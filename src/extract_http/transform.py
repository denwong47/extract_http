# Basic transformations for extraction time convenience.
# Useful for 


import warnings

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
import math
import re
import string
from typing import Iterable, Union, List
from urllib.parse import urljoin

from extract_http.bin import curl, \
                             formatters, \
                             safe_zip, \
                             text_to_bool
from extract_http.record_dict import record_dict

from extract_http.defaults import RECORD_DICT_DELIMITER

class native_list(list):
    """
    Empty wrapper around list so that we can identify the type of list using isinstance()

    A native list is a dict where dict[key] is a list.
    Used with record_dict.
    """
    pass

class iterated_list(list):
    """
    Empty wrapper around list so that we can identify the type of list using isinstance()
    
    An iterated list is a record_dict where it contained a list of dictionaries, and each dict[key] contains a scalar value.
    When record_dict.get(key) is used and iterate_list is True, record_dict will return a list containing all the values from each dictionary sequentially.
    Used with record_dict.
    """
    pass

class ArithmaticCalculationError(ValueError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class ArithmaticCalculationType(Enum):
    """
    Enum Class that is used in formatter.
    
    """
    SUM = "sum"
    MINUS = "minus"
    MULTIPLY = "mul"
    DIVIDE = "div"
    MAX = "max"
    MIN = "min"
    POWER = "power"

    @classmethod
    def function_list(cls):
        return cls._value2member_map_

    def get_function(self):
        _function_switch = {
            type(self).SUM: sum,
            type(self).MINUS: lambda iterables: sum(
                (_iterable * (1-2*(_id>0)) for _id, _iterable in enumerate(iterables))
            ),
            type(self).MULTIPLY: math.prod,
            type(self).DIVIDE: lambda iterables: math.prod(
                (_iterable ** (1-2*(_id>0)) for _id, _iterable in enumerate(iterables))
            ),
            type(self).MAX: max,
            type(self).MIN: min,
            type(self).POWER: power,
        }
        return _function_switch.get(self, None)

    def execute(self, iterables:Iterable):
        iterables = get_numeric_value(iterables)
        _func = self.get_function()

        if (callable(_func)):
            return _func(iterables)
        else:
            return ArithmaticCalculationError(f"Cannot Execute arithmatic calculation - type '{self.value}' not defined.")

def power(
    iterables:Iterable,
):
    _return = None

    for _iterable in iterables:
        if (_return is None):
            _return = _iterable
        else:
            _return **= _iterable
    
    return _return

def get_numeric_value(
    text: str,
    return_err: bool=True,
)->Union[float,int]:
    if (isinstance(text, list) and not isinstance(text, str)):
        value = []
        for _item in text:
            _item_value = get_numeric_value(_item, return_err=return_err)

            if (not isinstance(_item_value, Exception) or return_err):
                value.append(_item_value)

    else: 
        try:
            value = float(text)
        except ValueError as e:
            return ArithmaticCalculationError(str(e))

        if (value.is_integer()):
            value = int(text)
        
    return value

# General Arithmatic Calculations with supplied parameters and strings:
# For use with extract_http.transform.transform_formatter only.
def maths_transformation(
    kind,
):
    def _func(
        _value,
        _params,
    ):
        return ArithmaticCalculationType(kind).execute([_value, *_params])

    return _func

# Custom Formatter class to allow for additional transformations.
class transform_formatter(string.Formatter):
    """
    Special String Formatter.

    Takes the value and do basic arithmatic transformations BEFORE passing onto standard String Formatter.
    It works by using $ to denote the start of transformations, with each subsequent ones delimiteed by commas. Each transformation is sequentially applied.

    Example:
        salary:,.2f$mul(1.3),sum(2000)
    This will 
    1. look for the value of salary,
    2. muliply the value by 1.3,
    3. add 2000 on the resultant value, then
    4. display it as a comma separated two decimal floating point.

    3 Types of Transformations are hardcoded:
    - $upper            - Upper Case transformation
    - $lower            - Lower Case transformation
    - $strip(char)      - Remove all occurances of spaces or char, if specified.
    
    Other transformations are defined under ArithmaticCalculationType.

    Parameters to the transformation is supplied in (param1, param2,...), the whole structure of which is optional.
    Excess parameters are discarded without warning.

    This is mostly used for conversion of units.
    """
    def format_field(self, value, format_spec):
        if ("$" in format_spec):
            transform_syntax = r"(?P<type>[\w_]+)(?:\((?P<params>[^\)]+)\))?,?"
            python_format_spec, transform_format_spec = format_spec.split("$", maxsplit=1)

            _transform_switch = {
                "upper":lambda _value, _params: str(_value).upper(),
                "lower":lambda _value, _params: str(_value).lower(),
                "strip":lambda _value, _params: str(_value).replace(_params.pop(0) if _params else " ", ""),
                **{
                    _kind: maths_transformation(_kind)
                        for _kind in ArithmaticCalculationType.function_list()
                },
                None: lambda _value, _params: _value,
            }

            # For each Transformation
            for _match in re.finditer(transform_syntax, transform_format_spec, ):
                _type = _match.group("type")
                _params = _match.group("params").split(",") if _match.group("params") else []

                value = _transform_switch.get(_type.lower(), _transform_switch[None])(value, _params)
                
        else:
            # If $ doesn't exist to begin with, the pass the whole format_spec.
            python_format_spec = format_spec
            transform_format_spec = []
            
        return super().format_field(value, python_format_spec)


# Transform a single record
def transform_record(
    transform:dict,
    record:dict,
    url:str=None,
    delimiter:str=RECORD_DICT_DELIMITER,
)->dict:
    """
    Main function to apply transformations from transform onto record.
    url is supplied to calculate full url from relative ones; needed for base64.
    delimiter is used for nested key strings in form of "key1>>>key1a>>>key1ai".
    """

    def vectorise(func):
        """
        Decorator for transformation function.

        Vectorise a transformation to allow for lists to be transformed by iteration.
        """

        def wrapper(*args, **kwargs):
            _source = kwargs.get("source", None)

            if (isinstance(_source, list) and not isinstance(_source, str)):
                _return = [ func(*args, **{
                        **kwargs,
                        "source":_subsource
                    } ) for _subsource in _source ]
                # with ThreadPoolExecutor() as executor:
                #     _mapper = lambda subsource: func(*args, **{
                #         **kwargs,
                #         "source":subsource
                #     } )

                #     _return = executor.map(
                #         _mapper,
                #         list(_source)
                #     )
            else:
                _return = func(*args, **kwargs)
            
            return _return

        return wrapper

    # @vectorise can't work here:
    # This is a special case where source is not the record[key] but the source str.
    # we need to look at record and figure out if any {obj} used is a list; if so, return a list capturing all of them.
    # It is assumed that if some of them are lists, they would have the same length.
    def get_source(
        source:str,
        record:record_dict,
        delimiter:str=RECORD_DICT_DELIMITER,
    ):
        """
        Get source data to be passed to transformations.

        source is a python format string, in which nested keys are allowed.
        record is the record_dict object containing the entire set of data from "locate>>>search_root".

        delimiter is a string defining the delimiter used in source.
        """

        # Work out if there is a list involved in the formatters
        _list_count = None

        # Resolve the magic_keywords first (potential security risk? magic_keywords can invoke trigger formatters.)
        source = magic_keywords(source)

        if (isinstance(record, dict) and \
            not isinstance(record, record_dict)):
            record = record_dict(record)

        # Establishing list count
        if (_formatters := tuple(formatters(source))):
            # If there are formatters to begin with
            for _formatter in _formatters:
                
                _subrecord = record.get(
                    _formatter,
                    None,
                    delimiter=delimiter,
                    iterate_lists=True,
                    flatten_lists=True,
                )
                
                if (isinstance(_subrecord, list)):
                    # Check if its natively a list
                    if (isinstance(record.get(
                        _formatter,
                        None,
                        delimiter=delimiter,
                        iterate_lists=False, # False here
                        flatten_lists=True,
                    ), list)):
                        is_native_list = True
                    else:
                        is_native_list = False

                    _list_count = len(_subrecord)
                    break
        else:
            # If there is are no formatters to begin with, we can simply return the constant, with the magic_keywords() already applied.
            return source

        
        _return = []
        
        # So we have a list to deal with.

        # First we create a generator of ( [_subrecord1_attr1, _subrecord1_attr2,... ], [_subrecord2_attr1, _subrecord2_attr2,... ], [_subrecord3_attr1, _subrecord3_attr2,... ], )
        _subrecords = safe_zip(*[record.get(
            _formatter,
            None,
            delimiter=delimiter,
            iterate_lists=True,
            flatten_lists=True,
        ) for _formatter in formatters(source)], repeat_last=True)
        # Using repeat_last allows anything that is not a list to be repeated.
        # This generator does not contain the formatter name itself.

        # So we dig into each subrecord:
        for _subrecord in _subrecords:
            # And rebuild the subrecord as a dict { attr1:_subrecord1_attr1, attr2:_subrecord1_attr2, attr3:_subrecord1_attr3,}...
            _subrecord = record_dict({
                _key:_value \
                    for _key, _value in zip(formatters(source), _subrecord)
            })

            # Do the formatting
            _value = transform_formatter().format(source, **_subrecord)

            _return.append(_value)
        
        if (_list_count is not None):
            if is_native_list:
                return native_list(_return)
            else:
                return iterated_list(_return)
        else:
            if (len(_return)>0):
                return _return.pop(0)
            else:
                return None
        # else:
        #     return source.format(**record)




    _recognised_keywords = {
        "UTC_ISO":lambda : datetime.utcnow().isoformat(),
        "UTC_UNIX":lambda : str(datetime.utcnow().timestamp()),
    }

    def magic_keywords(
        text:str,
    ):
        """
        Magic Keywords are special phrases that will automatically be substituted with predefined values.

        These are defined in _recognised_keywords.
        """

        if (isinstance(text, str)):
            for _keyword, _func in zip(_recognised_keywords, _recognised_keywords.values()):
                text = text.replace(f"%%{_keyword}", _func())
        
        return text

    @vectorise
    def change_type(
        type:str,
        source:str,
    ):
        """
        key "type"

        Change object type for value.
        """

        _type_switch = {
            "int":int,
            "str":str,
            "float":float,
            "bool":text_to_bool,
            "bytes":lambda text: text.encode("utf-8"),
        }
        try:
            _return = _type_switch.get(type, str)(source)
        except (ValueError, TypeError) as e:
            # If failed, just return as is
            _return = source
        return _return

    # Does not need to vectorise this - ThreadPoolExecutor is embedded here
    def embed_base64(
        embed:str,
        source:str,
        url:str=None,
        params:dict=None,
    ):
        """
        key "embed"

        Use a source value as url, fetch the url, and put the resultant data as base64 value.

        Mostly used for embedding images.
        """

        _data = []

        if (source is not None):
            # Fetch URL
            if (embed == "url"):
                if (isinstance(url, str)):
                    prep_url = lambda _url: urljoin(url, _url)
                else:
                    prep_url = lambda _url: _url

                _urls = [ 
                    prep_url(_url) for _url in ([ source, ] if (not isinstance(source, list)) else source)
                ]
                
                with ThreadPoolExecutor() as executor:
                    _data = executor.map(lambda _url:curl(_url, params, encode="base64text"), _urls)

            _data = [
                (_result if (not isinstance(_result, Exception)) else None) for _result in list(_data)
            ]

            if (isinstance(source, str)):
                if (len(_data) <= 0):
                    return None
                else:
                    return _data[0]
            else:
                return _data
        else:
            return None

    @vectorise
    def make_substitution(
        substitute:dict,
        source:str,
    ):
        """
        key "subsitute"

        Regular Expression substitutions.
        """

        _pattern = substitute.get("pattern", None)
        _rep = substitute.get("rep", None)

        if (not all((_pattern, _rep))):
            warnings.warn(
                UserWarning(
                    f"Pattern '{_pattern}' or Replacement '{_rep}' not valid, skipping."
                )
            )
            _return = source
        else:  
            _return = re.sub(
                _pattern,
                _rep,
                source,
            )

        return _return

    @vectorise
    def split_value(
        delimiter:str,
        source:str,
    ):
        """
        key "split"

        Split values into a list using delimiter as sep.
        """

        # If delimiter is empty or not a string, default it to \s+
        if (len(delimiter)<=0 if isinstance(delimiter, str) else False):
            delimiter = None
        
        return [ _value.strip() for _value in  source.split(sep=delimiter) ]


    # Ensure record is a record_dict object, otherwise nested keys won't work
    record = record_dict(record)

    # Each _key in transform represents a new dict key
    # DO NOT PARALLELISE THIS - some subsequent transformations can require earlier ones
    for _key in transform:
        _source = transform[_key].get("source", None)
        _split = transform[_key].get("split", None)
        _type = transform[_key].get("type", None)
        _substitute = transform[_key].get("substitute", None)
        _embed = transform[_key].get("embed", None)

        # print (_key, _source, _split, _type, _substitute, _embed)

        # If source is not defined, assume its the key itself
        if (not(_source)):
            if (get_source(
                    source=f"{{{_key}}}",
                    record=record,
                    delimiter=delimiter,
                )):
                _source = f"{{{_key}}}"
            else:
                warnings.warn(f"Source not found for transform key {_key}, skipping.")
                continue

        # Create a lambda to get the destination value;
        # this is necessary because it changes after each successful transformation
        _destination_record_value = lambda iterate_lists: record.get(
                                                _key,
                                                default=None,
                                                delimiter=delimiter,
                                                iterate_lists=iterate_lists,
                                            )

        # Get the source value
        _source_record_value = get_source(
                source=_source,
                record=record,
                delimiter=delimiter,
            )

        # Check if the list returned is natively a list in the record.
        # Otherwise iterate_lists will just pop the first element of the list to the record and discard the rest.
        is_native_list = isinstance(_source_record_value, native_list)

        

        # Create the new key if doesn't exist yet
        record.put(
            _key,
            _source_record_value,
            delimiter=delimiter,
            iterate_lists=(not is_native_list),
            replace_list_items=True,
        )

        # SPLIT STRING
        if (_split):
            record.put(
                _key,
                split_value(
                    delimiter=_split, # This is not delimiter <<< - its a variable defined by the config
                    source=_destination_record_value(True),
                ),
                delimiter=delimiter,
                iterate_lists=False, # Don't iterate lists here - obviously we are expecting lists
                replace_list_items=True,
            )

        # REGEX SUBSTITUTION
        if (_substitute):
            record.put(
                _key,
                make_substitution(
                    substitute=_substitute,
                    source=_destination_record_value(True),
                ),
                delimiter=delimiter,
                iterate_lists=(not is_native_list),
                replace_list_items=True,
            )

        # EMBED BASE64
        if (_embed):
            record.put(
                _key,
                embed_base64(
                    embed=_embed,
                    source=_destination_record_value(True),
                    url=url,
                    ),
                delimiter=delimiter,
                iterate_lists=(not is_native_list),
                replace_list_items=True,
            )

        # TYPE CHANGE
        if (_type):
            record.put(
                _key,
                change_type(
                    type=_type,
                    source=_destination_record_value(True),
                    ),
                delimiter=delimiter,
                iterate_lists=(not is_native_list),
                replace_list_items=True,
            )
            
    return record
        