from bs4 import BeautifulSoup

from extract_http.bin import curl
from extract_http.exceptions import FileIOError, \
                                    HTMLParseError, \
                                    ConfigIncomplete
from extract_http.html_node import  find_all_nodes, \
                                    get_value_array, \
                                    get_value_lists, \
                                    get_value_records, \
                                    get_value_table
from extract_http.transform import  transform_record

from extract_http.defaults import RECORD_DICT_DELIMITER


def do_locate_html(
    locate:dict,
    html:str,
    url:str=None,
    delimiter:str=RECORD_DICT_DELIMITER,
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
        _table = _locate_group.get("table", None)

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
        elif (_table):
            _data_group = get_value_table(
                _table,
                _nodes,
            )

        _data_group = do_transform(
            _transform,
            _data_group,
            url=url,
            delimiter=delimiter,
        )
        
        _data.append(_data_group)

    return _data
    

def do_transform(
    transform:dict,
    data:list,
    url:str=None,
    delimiter:str=RECORD_DICT_DELIMITER,
)->list:
    if (isinstance(data, list)):
        # We need to replace the object of data itself, so we can't just throw away the return value
        for _id, _obj in enumerate(data):
            data[_id] = do_transform(
                transform,
                _obj,
                url=url,
                delimiter=delimiter,
            )
    elif (isinstance(data, dict)):
        data = transform_record(
            transform,
            data,
            url=url,
            delimiter=delimiter,
        )

    return data


def do_extract_html(
    config:dict,
    **kwargs,
    )->str:
    # Example
    _type = config.get("type", "").format(**kwargs)
    _url = config.get("url", "").format(**kwargs)
    _file = config.get("file", "").format(**kwargs)
    _params = config.get("params", {}).copy()
    _locate = config.get("locate", {}).copy()

    for _param in _params:
        if (_param in kwargs):
            _params[_param] = kwargs[_param]

    if (not (_type and (_url or _file) and _locate)):
        _exception = ConfigIncomplete("HTML Extraction missing configurations. Type, URL and Locate needs to be supplied.")
        raise _exception
        return _exception

    if (_file):
        try:
            with open(_file, "r") as _fHnd:
                _result = _fHnd.read()
        except Exception as e:
            _result = FileIOError(str(e))
    else:
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
    delimiter:str=RECORD_DICT_DELIMITER,
    **kwargs,
    )->dict:

    _type = config.get("type", "").format(**kwargs)
    _url = config.get("url", "").format(**kwargs)
    _file = config.get("file", "").format(**kwargs)
    _params = config.get("params", {})
    _transform = config.get("transform", None)

    for _param in _params:
        if (_param in kwargs):
            _params[_param] = kwargs[_param]
    
    if (not (_type and (_url or _file))):
        _exception = ConfigIncomplete("JSON Extraction missing configurations. Type, URL need to be supplied.")
        raise _exception

    if (_file):
        try:
            with open(_file, "r") as _fHnd:
                _result = _fHnd.read()
        except Exception as e:
            _result = FileIOError(str(e))
    else:
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
                delimiter=delimiter,
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