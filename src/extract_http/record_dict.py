"""
record_dict.py

A class of dict called record_dict, a subclass of dict.

Allows the getting and putting of data in nested dicts via delimited key strings, such as
    record_dict().get("key1>>>key2>>>key3")
refers to
{
    "key1":{
        "key2":{
            "key3": _obj
        }
    }
}
"""


from typing import Any, Union

class RecordNodeNotFound(ValueError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class record_dict(dict):
    def get(
        self,
        key:Union[str, list],
        default:Any=RecordNodeNotFound("Requested node does not exist."), # Using this instead of None allows default to be actually None
        delimiter:str=">>>",        # This a string literal because 
        iterate_lists:bool=True,
        flatten_lists:bool=True,
        **kwargs
    )->Any:
        """
        Like dict.get(), try to fetch a value via a key - but it can search nested dicts inside itself.

        The exact nesting is specified through delimited string - Default delimiter is ">>>", i.e.
            record_dict().get("key1>>>key2>>>key3")
        refers to
        {
            "key1":{
                "key2":{
                    "key3": _obj
                }
            }
        }

        If it fails, default is returned instead.

        In addition, iterate_lists allows the searching of keys inside records, i.e. List[Dict].
        If True, it will continue to search inside any lists it encounters, and look for dicts with the specified subkey instead.
        It will return the values in form of a list at that level.
        """

        if (isinstance(key, str)):
            key = key.split(delimiter)

        _first_key = key.pop(0)

        if (_first_key in self.keys()):
            _first_value = self[_first_key]

            if (len(key) <= 0):
                return _first_value
            else:
                if (isinstance(_first_value, dict)):
                    # Convert dict to record_dict before using the custom .get()
                    return type(self)(_first_value).get(
                        key,
                        default=default,
                        delimiter=delimiter,
                        **kwargs)
                elif (isinstance(_first_value, list)):
                    if (iterate_lists):
                        # If we are iterating lists, then we extract the list and flatten it.
                        _listed_values = [
                            (type(self)(_list_item).get(
                                key.copy(),
                                default=default,
                                delimiter=delimiter,
                                iterate_lists=iterate_lists,
                                flatten_lists=flatten_lists,
                                **kwargs) if (isinstance(_list_item, dict)) else _list_item) \
                                    for _list_item in _first_value
                        ]

                        _flattened_list = []
                        for _list_item in _listed_values:
                            if (isinstance(_list_item, list) and \
                                not isinstance(_list_item, str)):
                                _flattened_list += _list_item
                            else:
                                _flattened_list.append(_list_item)

                        return _flattened_list
                    else:
                        # If we are not iterating lists and we have not exhausted key
                        # Then key is deemed not found, 
                        # Return default.
                        return default
                else:
                    # If we haven't exhausted key and we already found a non-dict non-list object,
                    # then key is not found.
                    # Return default.
                    return default
                    
        else:
            return default

    def put(
        self,
        key:Union[str, list],
        value:Any,
        delimiter:str=">>>",
        iterate_lists:bool=True,
        replace_list_items:bool=True,
        **kwargs,
    )->None:
        """
        Opposite of get(), try to store a value via a key - but it can search nested dicts inside itself.

        The exact nesting is specified through delimited string - Default delimiter is ">>>", i.e.
            record_dict().put("key1>>>key2>>>key3")
        refers to
        {
            "key1":{
                "key2":{
                    "key3": _obj
                }
            }
        }

        If the key does not exists, it is created instead.

        In addition, iterate_lists allows the expansion of lists into records, i.e. List[Dict].
        If True, it will expect a list as value, and iterate through the items to put each one into one record under the specified subkey.

        """

        # Create node if it doesn't exist
        def create_node(
            self,
            first_key:str,
            remaining_keys:list,
            value:Any,
            delimiter:str=">>>",
            iterate_lists:bool=True,
            **kwargs,
            ):
            """
            The node must NOT exist; its much safer to use .put() in every single case.
            Hence this is an internal function of .put().
            """

            if (len(remaining_keys)>0):
                self[first_key] = type(self)()
                self[first_key].put(
                        remaining_keys,
                        value,
                        delimiter=delimiter,
                        iterate_lists=iterate_lists,
                    )
            else:
                self[first_key] = (value.pop(0) if iterate_lists else value)

            return None
        

        if (isinstance(key, str)):
            key = key.split(delimiter)

        if (not isinstance(value, list) or \
            isinstance(value, str)):
            value = [value,]

        """
        This has a slight problem of actually wanting to put([]) into the values;
        but if that is the case, iterate_lists simply doesn't make sense, so we just return None and finish the iteration.
        """
        if (len(value) <= 0 and iterate_lists):
            return None

        _first_key = key.pop(0)

        if (_first_key in self.keys()):
            _first_value = self[_first_key]
            if (len(key) <= 0):
                if (isinstance(_first_value, list) and \
                    not isinstance(_first_value, str)):
                    _element_count = len(self[_first_key])
                    self[_first_key] = value[:_element_count] if iterate_lists else value

                    for _ in range(_element_count):
                        # We cannot use
                        #   value = value[_element_count:]
                        # because we have to keep the same mutable object
                        value.pop(0)
                else:
                    self[_first_key] = value.pop(0) if iterate_lists else value
                return None
            else:
                if (isinstance(_first_value, dict)):
                    # Convert dict to record_dict before using the custom .get()
                    self[_first_key] = type(self)(_first_value)
                    return self[_first_key].put(
                        key,
                        value,
                        delimiter=delimiter,
                        iterate_lists=iterate_lists,
                        **kwargs)
                elif (isinstance(_first_value, list) and \
                    not isinstance(_first_value, str)
                    ):
                    if (iterate_lists):
                        # If we are iterating lists, then we extract the list and flatten it.
                        for _item_id, _list_item in enumerate(_first_value):
                            if (isinstance(_list_item, dict)):
                                self[_first_key][_item_id] = type(self)(self[_first_key][_item_id])
                            else:
                                # The original list item is not a dict, but our key isn't exhausted.
                                # We have to wipe the original value for a new dict.
                                if (replace_list_items):
                                    self[_first_key][_item_id] = type(self)()
                                else:
                                    # If we are not replacing these list items,
                                    # leave the list items as is.
                                    continue

                            self[_first_key][_item_id].put(
                                key.copy(),
                                value, # We don't need to pop this, value is mutable and thus "passed by reference"
                                delimiter=delimiter,
                                iterate_lists=iterate_lists,
                                **kwargs)
                    else:
                        self[_first_key] = value
                else:
                    self[_first_key] = type(self)()
                    return create_node(
                        self[_first_key],
                        key.pop(0),
                        key,
                        value,
                        delimiter=delimiter,
                        iterate_lists=iterate_lists,
                        **kwargs,
                        )
        else:
            return create_node(
                        self,
                        _first_key,
                        key,
                        value,
                        delimiter=delimiter,
                        iterate_lists=iterate_lists,
                        **kwargs,
                        )


# if __name__=="__main__":
# _dict = {
#     "a":{
#         "b":{
#             "c":{
#                 "d":"Something",
#             }
#         }
#     },
#     "123":True,
#     "456":[
#         {
#             "abc":[
#                 "def",
#                 "def2",
#                 "def3",
#             ]
#         },
#         {
#             "abc":"ghi",
#         },
#         "a string",
#     ]
# }

#     _dict = record_dict(_dict)

#     print (_dict.get("123", delimiter=">>>"))
#     print (_dict.put(
#         "456>>>abc", [0,9,8,7,6,5,4,3,2], delimiter=">>>", replace_list_items=True
#     ))

#     print (_dict)