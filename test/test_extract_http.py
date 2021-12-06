import os, sys
import unittest
from typing import DefaultDict, Union

import numpy as np

from extract_http.html_node import get_value_array, get_node_value, parse_node_format, NodeFormatStringInvalid
from extract_http.extract import extract
from extract_http.transform import transform_record
from extract_http.record_dict import record_dict
from extract_http.defaults import RECORD_DICT_DELIMITER

class TestCaseFileIOError(IOError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__

class TestCasePickleCorrupted(RuntimeError):
    def __bool__(self):
        return False
    __nonzero__ = __bool__


def read_file(
    path:str,
    output:type=str
)->Union[str, bytes]:
    try:
        with open(path, f"r{'b' if output is bytes else ''}") as _fHnd:
            _return = _fHnd.read()
    except Exception as e:
        _return = TestCaseFileIOError(str(e))

    return _return

_test_data = None

def setUpModule() -> None:
    global _test_data
    
    _file_names = [
        "erco_articlegroups",
        "erco_specsheet_A2000292.json",
    ]

    _test_data = {
        _file_name: \
            read_file(
                TestExtractHTTP.get_testdata_path(f"{_file_name}.json"),
                output=str,
            ) for _file_name in _file_names
    }



class TestExtractHTTP(unittest.TestCase):

    @classmethod
    def get_testcase_pickle_name(cls, function_name, testcase_id=1):
        return f"testcase_test_{function_name:s}_{testcase_id:02d}"

    @classmethod
    def get_testdata_path(cls, filename:str)->str:
        return os.path.join(cls.get_testdata_dir(), filename)

    @classmethod
    def get_testdata_dir(cls):
        return os.path.join(
            os.path.dirname(sys.argv[0]),
            "data/"
            )

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def conduct_tests(
        self,
        func,
        tests:dict,
        ):

        for _test in tests:
            if (issubclass(_test["answer"], Exception) if (isinstance(_test["answer"], type)) else False):
                with self.assertRaises(Exception) as context:
                    _return = func(
                        **_test["args"]
                    )
                    if (isinstance(_return, Exception)):
                        raise _return

                self.assertTrue(isinstance(context.exception, _test["answer"]))
            elif (isinstance(_test["answer"], type)):
                self.assertTrue(isinstance(func(**_test["args"]), _test["answer"]))
            elif (isinstance(_test["answer"], np.ndarray)):
                if (_test["answer"].dtype in (
                    np.float_,
                    np.float16,
                    np.float32,
                    np.float64,
                    np.float128,
                    np.longfloat,
                    np.half,
                    np.single,
                    np.double,
                    np.longdouble,
                )):
                    _assertion = np.testing.assert_allclose
                else:
                    _assertion = np.testing.assert_array_equal

                _assertion(
                    func(
                        **_test["args"]
                    ),
                    _test["answer"],
                )

            else:
                self.assertEqual(
                    func(
                        **_test["args"]
                    ),
                    _test["answer"],
                )

    def test_parse_node_format(self) -> None:
        _tests = [
            { "args": { "format": ">abc#125" }, "answer": NodeFormatStringInvalid },
            { "args": { "format": "div" }, "answer": {'selector': 'div', 'id': None, 'source': 'innerHTML', 'subsource': None} },
            { "args": { "format": "table>tr" }, "answer": {'selector': 'table>tr', 'id': None, 'source': 'innerHTML', 'subsource': None} },
            { "args": { "format": "table>tr>td#0" }, "answer": {'selector': 'table>tr>td', 'id': 0, 'source': 'innerHTML', 'subsource': None} },
            { "args": { "format": "table>tr>td#0$innerHTML" }, "answer": {'selector': 'table>tr>td', 'id': 0, 'source': 'innerHTML', 'subsource': None} },
            { "args": { "format": "table>tr>td$innerHTML" }, "answer": {'selector': 'table>tr>td', 'id': None, 'source': 'innerHTML', 'subsource': None} },
            { "args": { "format": "table>tr>td>img#0$attr" }, "answer": {'selector': 'table>tr>td>img', 'id': 0, 'source': 'attr', 'subsource': 'id'} },
            { "args": { "format": "table>tr>td>img#0$attr[src]" }, "answer": {'selector': 'table>tr>td>img', 'id': 0, 'source': 'attr', 'subsource': 'src'} },
            { "args": { "format": "table>tr>td>img$attr[src]" }, "answer": {'selector': 'table>tr>td>img', 'id': None, 'source': 'attr', 'subsource': 'src'} },
        ]

        self.conduct_tests(
            parse_node_format,
            _tests
        )

    def test_transform_record(self) -> None:
        _tests = [
            # Test as per README.md (Nested Dicts/Key Strings)
            {
                "args": {
                    "transform":{
                        "Employment>>>Terms":{
                            "source":"[{Name} shall be paid ${Employment>>>Salary:,d} annually for the {Employment>>Contract Type}Role of {Employment>>Role}.]",
                        }
                    },
                    "record":{
                        "Name":"John Doe",
                        "Age":"35",
                        "Email":"john.doe@sample.com",
                        "Employment":{
                            "Contract Type":"Permanent",
                            "Role":"Backend Developer",
                            "Salary":"40000",
                        }
                    },
                    "url":"https://www.test.com",
                    "delimiter":RECORD_DICT_DELIMITER,
                },
                "answer": {
                    "Name":"John Doe",
                    "Age":"35",
                    "Email":"john.doe@sample.com",
                    "Employment":{
                        "Contract Type":"Permanent",
                        "Role":"Backend Developer",
                        "Salary":"40000",
                        "Terms":"John Doe shall be paid $40,000 annually for the Permanent Role of Backend Developer.",
                    }
                }
            },
            # Test as per README.md (transform > [parameter_name] > type)
            {
                "args": {
                    "transform":{
                        "Age":{
                            "type":"int"
                        }
                    },
                    "record":{
                        "Name":"John Doe",
                        "Age":"35",
                        "Email":"john.doe@sample.com",
                    },
                    "url":"https://www.test.com",
                    "delimiter":RECORD_DICT_DELIMITER,
                },
                "answer": {
                    "Name":"John Doe",
                    "Age":35,
                    "Email":"john.doe@sample.com",
                }
            },
            # Test list values
            {
                "args": {
                    "transform":{
                        "new_description":{
                            "source":"NEW LINE: {description}",
                        }
                    },
                    "record":{
                        "description": [
                            "Housing: cast aluminium, designed as heat sink, with connection cable L 500mm. Fixing ring: polymer, black.",
                            "Mounting ring: polymer, white (RAL9002). Mounting for ceiling thicknesses of 1-30mm.",
                            "10-pole connection terminal. Through-wiring possible.",
                            "Includes DALI control gear.",
                            "LED module: mid-power LEDs.",
                            "Fresnel lens made of optical polymer.",
                            "Anti-glare cone: polymer, white (RAL 9002).",
                            "The luminaire is protected on the room side against splashing water.",
                            "Recess depth 120mm for DALI control gear.",
                            "Protection Class II",
                            "Weight 1.38kg",
                            "Available from 10.2021"
                        ]
                    },
                    "url":"https://www.erco.com",
                    "delimiter":RECORD_DICT_DELIMITER,
                },
                "answer": {
                    "description": [
                        "Housing: cast aluminium, designed as heat sink, with connection cable L 500mm. Fixing ring: polymer, black.",
                        "Mounting ring: polymer, white (RAL9002). Mounting for ceiling thicknesses of 1-30mm.",
                        "10-pole connection terminal. Through-wiring possible.",
                        "Includes DALI control gear.",
                        "LED module: mid-power LEDs.",
                        "Fresnel lens made of optical polymer.",
                        "Anti-glare cone: polymer, white (RAL 9002).",
                        "The luminaire is protected on the room side against splashing water.",
                        "Recess depth 120mm for DALI control gear.",
                        "Protection Class II",
                        "Weight 1.38kg",
                        "Available from 10.2021"
                    ],
                    "new_description": [
                        "NEW LINE: Housing: cast aluminium, designed as heat sink, with connection cable L 500mm. Fixing ring: polymer, black.",
                        "NEW LINE: Mounting ring: polymer, white (RAL9002). Mounting for ceiling thicknesses of 1-30mm.",
                        "NEW LINE: 10-pole connection terminal. Through-wiring possible.",
                        "NEW LINE: Includes DALI control gear.",
                        "NEW LINE: LED module: mid-power LEDs.",
                        "NEW LINE: Fresnel lens made of optical polymer.",
                        "NEW LINE: Anti-glare cone: polymer, white (RAL 9002).",
                        "NEW LINE: The luminaire is protected on the room side against splashing water.",
                        "NEW LINE: Recess depth 120mm for DALI control gear.",
                        "NEW LINE: Protection Class II",
                        "NEW LINE: Weight 1.38kg",
                        "NEW LINE: Available from 10.2021"
                    ]
                }
            },
        ]

if __name__ == "__main__":
    unittest.main()