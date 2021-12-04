import pkgutil
import re
import json
import unicodedata
from bs4 import BeautifulSoup

from extract_http.bin import safe_zip

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

def find_all_nodes(
    find_all:list,
    soup:BeautifulSoup,
)->list:
    if (isinstance(find_all, str)):
        find_all = [find_all, ]

    # The first call will be a simple BeautifulSoup object, while all subsequent ones would have been resulted from a do_locate_html_find_all themselves, so a list of nodes.
    if (not isinstance(soup, list)):
        _parent_nodes = [soup, ]
    else:
        _parent_nodes = soup

    for _search in find_all:
        _children_nodes = []

        for _parent_node in _parent_nodes:
            if (isinstance(_search, str)):
                _children_nodes = _children_nodes + _parent_node.select(_search)
            else:
                _children_nodes = _children_nodes + _parent_node.find_all(
                    *_search.get("args", []),
                    **_search.get("kwargs", {}),
                )
        
        _parent_nodes = _children_nodes

    return _parent_nodes

def parse_node_format(
    format:str,
    allow_list:bool=True,
):
    # [
    #     "a#125",
    #     "div",
    #     "table>tr",
    #     "table>tr>td#0",
    #     "table>tr>td#0.innerHTML",
    #     "table>tr>td.innerHTML",
    #     "table>tr>td>img#0.attr[src]",
    #     "table>tr>td>img.attr[src]",
    # ]
    _pattern = r"^(?P<selector>[^>][^#\s]*?)(?:#?(?P<id>\d+))?(?:\$(?P<source>(?:innerHTML|innerText|stripText|attr|outerHTML))(?:\[(?P<subsource>[^\]]+)\])?)?$"

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

def get_node_value(
    format:list,
    nodes:BeautifulSoup,
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
        _source_switch = {
            "innerHTML":lambda node, subsource: node.decode_contents(),
            "innerText": lambda node, subsource: node.get_text(),
            "stripText": lambda node, subsource: strip_text(node.get_text()),
            "attr":lambda node, subsource: node.attrs.get(subsource, None),
            "outerHTML": lambda node, subsource: str(node),
        }

        extract = lambda value: unicodedata.normalize(
            "NFKD",
            _source_switch.get(
                _formatter["source"],
                _source_switch["innerHTML"]
            )(
                value,
                _formatter["subsource"]
            ).strip())

        if (_formatter["id"] is None):
            # Take all values as a list
            _return = [ extract(_value_node) for _value_node in _value_nodes ]
        else:
            # Take one element
            _return = extract(_value_nodes[_formatter["id"]])

        return _return
    else:
        return None



def get_value_array(
    key_format:str,
    value_format:str,
    nodes:BeautifulSoup,
): 
    _data = {}

    if (not isinstance(nodes, list)):
        nodes = [nodes, ]

    for _node in nodes:
        _key = get_node_value(key_format, _node)
        _value = get_node_value(value_format, _node)

        _data[_key] = _value

    # This needs to be enclosed in a list to be form a record... of 1No
    #     in order to match the output of get_value_records()
    return [_data, ]

def get_value_lists(
    values:dict,
    nodes:BeautifulSoup
)->dict:

    _dicts = {
        _key:get_node_value(
            values[_key], nodes,
        ) for _key in values
    }

    return _dicts

def get_value_records(
    values:dict,
    nodes:BeautifulSoup,
)->list:

    _dicts = get_value_lists(
        values,
        nodes,
    )

    if _dicts:
        _data = [ dict(zip(_dicts.keys(), _record)) for _record in safe_zip(*_dicts.values()) ]
    else:
        _data = []

    return _data

# Need to transfer these over to unittest

# _formats = [
#     "abc#125",
#     "div",
#     "table>tr",
#     "table>tr>td#0",
#     "table>tr>td#0.innerHTML",
#     "table>tr>td.innerHTML",
#     "table>tr>td>img#0.attr",
#     "table>tr>td>img#0.attr[src]",
#     "table>tr>td>img.attr[src]",
# ]

# {'selector': 'abc', 'id': '125', 'source': 'innerHTML', 'subsource': None}
# {'selector': 'div', 'id': 0, 'source': 'innerHTML', 'subsource': None}
# {'selector': 'table>tr', 'id': 0, 'source': 'innerHTML', 'subsource': None}
# {'selector': 'table>tr>td', 'id': '0', 'source': 'innerHTML', 'subsource': None}
# {'selector': 'table>tr>td', 'id': '0', 'source': 'innerHTML', 'subsource': None}
# {'selector': 'table>tr>td', 'id': 0, 'source': 'innerHTML', 'subsource': None}
# {'selector': 'table>tr>td>img', 'id': '0', 'source': 'attr', 'subsource': 'id'}
# {'selector': 'table>tr>td>img', 'id': '0', 'source': 'attr', 'subsource': 'src'}
# {'selector': 'table>tr>td>img', 'id': 0, 'source': 'attr', 'subsource': 'src'}

# for _format in _formats:
#     print (get_node_value (_format, BeautifulSoup()))
