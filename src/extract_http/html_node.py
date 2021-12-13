import re
import typing
from typing import Union
import io
import unicodedata
import warnings

from bs4 import BeautifulSoup
import bs4.element
import numpy as np
import pandas as pd



from extract_http.bin import safe_zip, find_all_nodes
from extract_http.html_table import TableOrientation, html_table
from pandas.io.pytables import Table


class NodeFormatStringInvalid(ValueError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

def strip_text(
    text:str,
    search:str=r"\s+",
    rep:str=" "
):
    return re.sub(
        search,
        rep,
        text
    )


def parse_node_format(
    format:str,
    allow_list:bool=True,
):
    # Select Strings
    # [<selector>][#<id>][$(innerHTML|innerText|stripText|outerHTML|attr[ATTR_NAME])]
    # Several things to note:
    # <selector> cannot start with a $ - that will confuse it with <source>.
    _pattern = r"^(?P<selector>[^>$][^#\s]*?)?(?:#(?P<id>-?\d+))?(?:\$(?P<source>(?:innerHTML|innerText|stripText|attr|outerHTML))(?:\[(?P<subsource>[^\]]+)\])?)?$"

    _matchobj = re.match(_pattern, format)
    if (_matchobj):
        _return = _matchobj.groupdict()

        if (not _return["id"]):
            _return["id"]=None if allow_list else 0
        else:
            _return["id"]=int(_return["id"])
        if (not _return["source"]): _return["source"]="innerHTML"
        if (_return["source"]=="attr" and not _return["subsource"]): _return["subsource"]="id"

        return _return
    else:
        return NodeFormatStringInvalid(f"{format} is not a valid Node Value formatter.")

# This is purely to deal with $innerHTML, $innerText, etc suffices
def get_node_attrvalue(
    node:bs4.element.Tag,
    source:str,
    subsource:str,
)->str:

    if (node is not None):
        _source_switch = {
            "innerHTML":lambda node, subsource: node.decode_contents(),
            "innerText": lambda node, subsource: node.get_text(),
            "stripText": lambda node, subsource: strip_text(node.get_text()),
            "attr":lambda node, subsource: node.attrs.get(subsource, None),
            "outerHTML": lambda node, subsource: str(node),
        }

        _source_data = _source_switch.get(
                                            source,
                                            _source_switch["innerHTML"]
                                        )(
                                            node,
                                            subsource
                                        )

        if (_source_data):
            return unicodedata.normalize(
                    "NFKD",
                    _source_data.strip())
        else:
            return None
    else:
        return None


def get_node_value(
    format:list,
    nodes:bs4.element.Tag,
    allow_list:bool=True,
):
    if (isinstance(format, str) or \
        isinstance(format, dict)):
        format = [format, ]

    _value_nodes = nodes
    
    for _format_item in format:
        _formatter = parse_node_format(
            _format_item,
            allow_list=allow_list,
        )

        _value_nodes = find_all_nodes(
            _formatter["selector"],
            _value_nodes,
        )

    if (_value_nodes):
        extract = lambda value: get_node_attrvalue(value, _formatter["source"], _formatter["subsource"])

        if (_formatter["id"] is None):
            # Take all values as a list
            _return = [ extract(_value_node) for _value_node in _value_nodes ]
        else:
            # Take one element
            try:
                _return = extract(_value_nodes[_formatter["id"]])
            except IndexError as e:
                warnings.warn(RuntimeWarning(
                    f"ID #{_formatter['id']} out of range for nodes, only {len(_value_nodes)} No. found.."
                ))
                _return = None
        
        return _return
    else:
        return None



def get_value_array(
    key_format:str,
    value_format:str,
    nodes:bs4.element.Tag,
): 
    _data = {}

    if (not isinstance(nodes, list)):
        nodes = [nodes, ]

    for _node in nodes:
        _key = get_node_value(key_format, _node)
        _value = get_node_value(value_format, _node)

        # get_node_value() always return a list unless #id is specified
        if (isinstance(_key, list)):
            # Warn if key is longer than 1 - that's not normal.
            # To fix this, add #0 or #1... to your Format String so that it knows which one to look for.
            if (len(_key) > 1):
                warnings.warn(RuntimeWarning(
                    f"Multiple values found for {key_format}: {[_subkey for _subkey in _key]}; do you intend to add #0? Alternatively, search for a more specific node."
                ))

            _key = _key.pop(0)

        # get_node_value() always return a list unless #id is specified
        # If its a list with more than 1 element, that's fine
        # If its a list with only 1 element, then strip the list away
        if (isinstance(_value, list)):
            if (len(_value) == 1):
                _value = _value.pop(0)

        # Don't do anything if _key is []
        if (_key):
            _data[_key] = _value

    # This needs to be enclosed in a list to be form a record... of 1No
    #     in order to match the output of get_value_records()
    return [_data, ]

def get_value_lists(
    values:dict,
    nodes:bs4.element.Tag
)->dict:

    _dicts = {
        _key:get_node_value(
            values[_key], nodes,
        ) for _key in values
    }

    return _dicts

def get_value_records(
    values:dict,
    nodes:bs4.element.Tag,
)->list:

    _record_nodes = nodes if (isinstance(nodes, list)) else [nodes, ]
    
    _data = []

    for node in _record_nodes:
        _dicts = get_value_lists(
                    values,
                    node,
                ) 

        if _dicts:
            _record = [ dict(zip(_dicts.keys(), _record)) for _record in safe_zip(*_dicts.values()) ]
        else:
            _record = []

        _data += _record


    if (isinstance(nodes, list)):
        return _data
    else:
        return _data.pop(0)
            

def get_value_table(
    settings:dict,
    nodes:typing.List[
        Union[
            str,
            io.IOBase,
            bs4.element.Tag,
        ]
    ],    
    **kwargs,
)->list:
    # replace settings with override where present
    for _key in settings:
        if (_key in kwargs):
            settings[_key] = kwargs[_key]
            del(kwargs[_key])

    _orient = TableOrientation.HEADER_ROW if (settings.get("orient", "rows").lower() == "rows") else TableOrientation.INDEX_COL
    _key_index = settings.get("key_index", 0)
    _keys = settings.get("keys", {})

    # Outer join all the tables requested
    _html_table = None
    for _node in nodes:
        _obj = html_table.from_bs4_node(
            _node,
            _orient,
            _key_index
        )
    
        if (_html_table is None):
            _html_table = _obj
        else:
            _html_table.merge(_obj)

    if (_html_table):
        _return = _html_table.export(
            _keys
        )
    else:
        _return = []
    
    return _return