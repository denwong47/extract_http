import warnings

import re
import urllib.parse

from bs4 import BeautifulSoup

from extract_http.bin import curl
from extract_http.exceptions import HTMLParseError, \
                                    ConfigIncomplete
from extract_http.html_node import  find_all_nodes, \
                                    get_value_array, \
                                    get_value_lists, \
                                    get_value_records
from extract_http.transform import  transform_record



def do_locate_html(
    locate:dict,
    html:str,
    url:str=None,
)->list:
    _data = []

    try:
        _soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        _exception = HTMLParseError(str(e), html=html)
        raise _exception
        return _exception
    
    for _locate_group in locate:
        _nodes = find_all_nodes(
            _locate_group.get("search_root", None),
            _soup
        )
        
        _values = _locate_group.get("values", None)
        _array = _locate_group.get("array", None) or _locate_group.get("record", None)
        _lists = _locate_group.get("lists", None)

        _transform = _locate_group.get("transform", {})

        if (_values):
            _data_group = get_value_records(
                _values,
                _nodes,
            )
        elif (_lists):
            _data_group = [ get_value_lists(
                _lists,
                _nodes,
            ), ]
        elif (_array):
            _data_group = get_value_array(
                _array["key"],
                _array["value"],
                _nodes,
            )

        _data_group = do_transform(
            _transform,
            _data_group,
            url=url,
        )
        
        _data.append(_data_group)

    return _data
    

def do_transform(
    transform:dict,
    data:list,
    url:str=None,
)->list:
    if (isinstance(data, list)):
        for _obj in data:
            _obj = do_transform(
                transform,
                _obj,
                url=url,
            )
    elif (isinstance(data, dict)):
        _obj = transform_record(
            transform,
            data,
            url=url,
        )

    return data


def do_extract_html(
    config:dict,
    **kwargs,
    )->str:
    # Example
    _type = config.get("type", "").format(**kwargs)
    _url = config.get("url", "").format(**kwargs)
    _params = config.get("params", {})
    _locate = config.get("locate", {})

    if (not (_type and _url and _locate)):
        _exception = ConfigIncomplete("HTML Extraction missing configurations. Type, URL and Locate needs to be supplied.")
        raise _exception
        return _exception
    
    _result = curl(
        _url,
        _params,
        None,
    )

    if (not isinstance(_result, Exception)):
        _html = _result
        _data = do_locate_html(
            _locate,
            _html,
            url=_url,
        )

        return _data
    else:
        raise _result
        return _result

    
def do_extract_json(
    config:dict,
    **kwargs,
    )->dict:

    _type = config.get("type", "").format(**kwargs)
    _url = config.get("url", "").format(**kwargs)
    _params = config.get("params", {})
    _transform = config.get("transform", None)
    
    if (not (_type and _url)):
        _exception = ConfigIncomplete("JSON Extraction missing configurations. Type, URL need to be supplied.")
        raise _exception

    _result = curl(
        _url,
        _params,
        None,
    )

    if (not isinstance(_result, Exception)):
        _data = _result

        if (_transform):
            _data = do_transform(
                transform=_transform,
                data=_data,
                url=_url,
            )

        return _data
    else:
        raise _result
        return _result

def extract(
    config:dict,
    **kwargs,
)->list:
    _type = config.get("type", "").format(**kwargs)

    if (not _type):
        _exception = ConfigIncomplete("Extraction missing Type configuration.")
        raise _exception

    _func_switch = {
        "html":do_extract_html,
        "json":do_extract_json,
        None:lambda config: ConfigIncomplete("Configuration has does not have a 'type' key."),
    }

    return _func_switch.get(config.get("type", _func_switch[None]))(
        config,
        **kwargs,
    )