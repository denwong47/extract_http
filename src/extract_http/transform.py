import warnings

import re
from concurrent.futures import ThreadPoolExecutor

from urllib.parse import urljoin
from extract_http.bin import curl, \
                             formatters, \
                             safe_zip
from extract_http.record_dict import record_dict

from extract_http.defaults import RECORD_DICT_DELIMITER

def transform_record(
    transform:dict,
    record:dict,
    url:str=None,
    delimiter:str=RECORD_DICT_DELIMITER,
)->dict:

    # Allow the dict content to be a list and still apply the transformation by iteration
    def vectorise(func):
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
        # Work out if there is a list involved in the formatters
        _list_count = None

        if (isinstance(record, dict) and \
            not isinstance(record, record_dict)):
            record = record_dict(record)

        # Establishing list count
        for _formatter in formatters(source):
            _subrecord = record.get(
                _formatter,
                None,
                delimiter=delimiter,
                iterate_lists=True,
                flatten_lists=True,
            )
            
            if (isinstance(_subrecord, list) and \
                not isinstance(_subrecord, str)):
                _list_count = len(_subrecord)
                break

        
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
            _return.append(source.format(**_subrecord))
        
        if (_list_count):
            return _return
        else:
            if (len(_return)>0):
                return _return.pop(0)
            else:
                return None
        # else:
        #     return source.format(**record)

    @vectorise
    def change_type(
        type:str,
        source:str,
    ):
        _type_switch = {
            "int":int,
            "str":str,
            "float":float,
            "bool":bool,
            "bytes":lambda text: text.encode("utf-8"),
        }
        try:
            _return = _type_switch.get(type, str)(source)
        except ValueError as e:
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
        _data = []

        # Fetch URL
        if (embed == "url"):
            if (isinstance(url, str)):
                prep_url = lambda _url: urljoin(url, _url)
            else:
                prep_url = lambda _url: _url

            _urls = [ 
                prep_url(_url) for _url in ([ source, ] if isinstance(source, str) else source)
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

    @vectorise
    def make_substitution(
        substitute:dict,
        source:str,
    ):
        _pattern = substitute.get("pattern", None)
        _rep = substitute.get("rep", None)

        if (None in (_pattern, _rep)):
            warnings.warn(f"Pattern '{_pattern}' or Replacement '{_rep}' not valid, skipping.")
            _return = source
        else:  
            _return = re.sub(
                _pattern,
                _rep,
                source,
            )

        return _return

    record = record_dict(record)

    # Each _key in transform represents a new dict key
    # DO NOT PARALLELISE THIS - some subsequent transformations can require earlier ones
    for _key in transform:
        _source = transform[_key].get("source", None)
        _type = transform[_key].get("type", None)
        _substitute = transform[_key].get("substitute", None)
        _embed = transform[_key].get("embed", None)

        if (not(_source) and not (_key in record)):
            warnings.warn(f"Source not found for transform key {_key}, skipping.")
        else:
            if (_source is not None):
                # THIS IS BY VALUE ONLY - DO NOT ASSIGN TO IT
                _destination_record_value = lambda : get_source(
                                                        source=_source,
                                                        record=record,
                                                        delimiter=delimiter,
                                                    )

                # Create the new key if doesn't exist yet
                record.put(
                    _key,
                    _destination_record_value(),
                    delimiter=delimiter,
                    iterate_lists=True,
                    replace_list_items=True,
                )

            # REGEX SUBSTITUTION
            if (_substitute):
                record.put(
                    _key,
                    make_substitution(
                        substitute=_substitute,
                        source=_destination_record_value(),
                    ),
                    delimiter=delimiter,
                    iterate_lists=True,
                    replace_list_items=True,
                )

            # EMBED BASE64
            if (_embed):
                record.put(
                    _key,
                    embed_base64(
                        embed=_embed,
                        source=_destination_record_value(),
                        url=url,
                        ),
                    delimiter=delimiter,
                    iterate_lists=True,
                    replace_list_items=True,
                )

            # TYPE CHANGE
            if (_type):
                record.put(
                    _key,
                    change_type(
                        type=_type,
                        source=_destination_record_value(),
                        ),
                    delimiter=delimiter,
                    iterate_lists=True,
                    replace_list_items=True,
                )
            
    return record
        