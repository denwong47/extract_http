from __future__ import annotations # enable in class type hint of itself

from enum import Enum
from typing import List, Tuple, Union
import warnings

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import bs4.element

DEFAULT_TABLE_TAG_CONTENT = "$innerText"

from extract_http.bin import find_all_nodes

def create_tag(html:str)->bs4.element.Tag:
    if (html is not None and not pd.isna(html)):
        _node = BeautifulSoup(html, "html.parser")
        return _node.find()
    else:
        return None

def map_keys(
    index:str,
    node:bs4.element.Tag,
    keys:dict={},
):
    from extract_http.html_node import get_node_value

    _format_string = keys.get(index, DEFAULT_TABLE_TAG_CONTENT)

    # It is possible that the index is not present in all tables; then node will be None
    if (node is not None):
        _value = get_node_value(
            _format_string,
            node,
        )
    else:
        return None

    if (_value is None):
        return _value
    elif (isinstance(node, list)):
        return _value
    else:
        return _value.pop(0)


class TableOrientation(Enum):
    HEADER_ROW = 0
    INDEX_COL = 1

class html_table():
    def __init__(
        self,
        dataframe:pd.DataFrame,
        *args,
        **kwargs,
    ):
        self.dataframe = dataframe


    @classmethod
    def from_bs4_node(
        cls,
        obj:bs4.element.Tag,
        orient:TableOrientation=TableOrientation.HEADER_ROW,
        index:int=0,
    ):
        # Put the whole table into a list of lists
        _lists = cls._get_list_of_lists(obj)

        # Get numpy array
        _dataframe = cls._get_dataframe(_lists)

        if (orient is TableOrientation.INDEX_COL):
            _dataframe = _dataframe.transpose()

        _dataframe.columns = _dataframe.iloc[index,:]
        _dataframe.drop(index, inplace=True)

        return cls(_dataframe)

    # Put everything in a list of lists, to make it easier to handle
    @staticmethod
    def _get_list_of_lists(
        table:bs4.element.Tag,
        rows:Union[str, dict]={
            "args":[["tr"],],
        },
        cols:Union[str, dict]={
            "args":[["td", "th"],],
        },
    ):
        if (isinstance(table, list) and len(table)>1):
            warnings.warn(
                UserWarning("Multiple tables are supplied to html_table. If these tables have different columns, some columns may be lost. Use extract_http.http_node.get_value_table() for list of tables.")
            )

        _table_rows = find_all_nodes([rows,], table)
        _table_cells = [
            find_all_nodes([cols,], _table_row) for _table_row in _table_rows
        ]

        return _table_cells
        
    # Read through the first column and first row, determine through rowspan and colspan to figure out the table size.
    # This answer is absolute - because rowspan and colspan always expands rightward and downward,
    # the row[0] and col[0] are the only row and column that will always contain references to all members.
    @staticmethod
    def _get_shape(
        obj:List[List[bs4.element.Tag]],
    )->Tuple[int, int]:
        _first_row = 0
        _first_col = 0

        _col_count = sum([
            int(_cell.attrs.get("colspan", 1)) for _cell in obj[_first_row]
        ])
        _row_count = sum([
            int(_row[_first_col].attrs.get("rowspan", 1)) for _row in obj
        ])

        return (_row_count, _col_count)

    @classmethod
    def _get_dataframe(
        cls,
        obj:List[List[bs4.element.Tag]],
    )->pd.DataFrame:
        # Use first row and first column to determine shape
        _shape = cls._get_shape(obj)

        _array = np.full(
            _shape,
            np.nan,
            dtype=np.object_,
        )

        _dataframe = pd.DataFrame(_array)

        # OLD NUMPY ARRAY BASED SOLUTION
        # @np.vectorize
        # def np_isnan(x):
        #     if isinstance(x, type(np.nan)):
        #         return np.isnan(x)
        #     else:
        #         return False

        def _get_next_cell(row):
            _col_not_nan = _dataframe.iloc[row,:].isnull()

            if (_col_not_nan.any()):
                return _col_not_nan.idxmax()
            else:
                return None
            
            # OLD NUMPY ARRAY BASED SOLUTION
            # _col_not_nan = np.where(np_isnan(_array[row]))[0]
            # if (np.any(_col_not_nan)):
            #     return _col_not_nan[0]
            # else:
            #     return None
        
        def _get_next_row():
            _all_not_nan = _dataframe.apply(
                lambda row: row.isnull().any(),
                axis=0,
            )
            
            if (_all_not_nan.any()):
                return _all_not_nan.idxmax()
            else:
                return None

            # OLD NUMPY ARRAY BASED SOLUTION
            # _all_not_nan = np.where(np_isnan(_array.flatten(order="C")))[0]
            # if (np.any(_all_not_nan)):
            #     return _all_not_nan[0]// _array.shape[1]
            # else:
            #     return None

        _row_id = -1
        
        for _table_row in obj:
            _row_id = max(_row_id+1, _get_next_row()) # ensure the iteration always go forward even with malformed HTML
            for _table_cell in _table_row:
                _rowspan = int(_table_cell.attrs.get("rowspan", 1))
                _colspan = int(_table_cell.attrs.get("colspan", 1))

                _col_id = _get_next_cell(_row_id)

                if (_col_id is not None):

                    # OLD NUMPY ARRAY BASED SOLUTION
                    # _array[
                    #     _row_id:min(_shape[0], _row_id+_rowspan),
                    #     _col_id:min(_shape[1], _col_id+_colspan)
                    # ] = _table_cell

                    _dataframe.iloc[
                        _row_id:min(_shape[0], _row_id+_rowspan),
                        _col_id:min(_shape[1], _col_id+_colspan)
                    ] = str(_table_cell)
                    # We are turning _table_cell into a string because pd.DataFrame automatically converts a Tag into a NavigableString, which loses all the attrs.
                    # Its not very efficient, perhaps one day we'll turn this into a full Python List implementation...
                
        return _dataframe

    def export(
        self,
        keys:dict={}, # decides what to use as values out of the nodes
    ):

        if (isinstance(self.dataframe, pd.DataFrame)):
            # We can't really use to_dict() as we wanted if we want to re-apply Tags into it
            # _dict = self.dataframe.to_dict(orient="records")

            _records = []

            for _index, _row in self.dataframe.iterrows():
                _dict = {}
                for _key, _value in _row.iteritems():
                    _record_key = create_tag(_key).text.strip().replace("\n", " ")
                    _record_value = map_keys(
                        _record_key,
                        create_tag(_value),
                        keys
                    ) or _dict.get(_record_key, None)
                    _dict[_record_key] = _record_value
                    
                _records.append(_dict)

            return _records
        else:
            pass

    def merge(
        self,
        other:html_table,
    ):
        if (isinstance(other, html_table)):
            self.dataframe = self.dataframe.merge(
                other.dataframe,
                how="outer",
            )
        else:
            return self
