# extract_http
 Web Scraping through configuration dictionaries


## extract_http.extract.extract

Extract information from a HTML or JSON API as according to a configuration dictionary.
```
def extract(
    config:dict,
    **kwargs,)
->list
```

# Configuration Dictionary
Example in YAML format:
```
type: html
url: https://lightfinder.erco.com/specsheets/show/{art_no:s}/en/
params:
    api: v1.1
locate:
    - search_root:
        - div.specsheet-header
      values:
        art_no: h4.spec-articlenumber
        art_name: h3.specsheet-title$stripText
    - search_root:
        - table.specs-table>tr
      array:
        key: td#0
        value: td#1$stripText
      transform:
        art_no:
            source: "{URL}"
            substitute:
                pattern: "^.+/(?P<art_no>[A\\d\\.]+)/$"
                rep: "\\g<art_no>"
        description:
            source: "{art_no} {Light distribution} light in {Colour of light} colour"
        Weight:
            substitute:
                pattern: "^(?P<numeric_weight>[\\d\\.]+)\\s*kg$"
                rep: "\\g<numeric_weight>"
            type: float
    - search_root:
        - div.description>ul
      lists:
        description: li.-entry$stripText
    - search_root:
        - div.acceccoir
      values:
        img_src: img.product-image$attr[src]
        img_alt: img.product-image$attr[alt]
        art_no: span.access-articlenumber
        descripton: span.access-name
        manual_pdf: div.access-download.access-manual>a$attr[href]
        specsheet_pdf: div.access-download.access-specsheet>a$attr[href]
      transform:
        img_base64:
            source: "{img_src}"
            embed: url
        manual_base64:
            source: "{manual_pdf}"
            embed: url
```

## > type
String, One of the following:
- html
- json

Defines type of information to parse; use the correct type relating to the output of the desired API.

HTML will be parsed by BeautifulSoup4.

## > url
String.

URL to request for data.
The URL will be formatted by `kwargs` (`url.format(**kwargs)`), where `kwargs` are all the keyword parameters supplied to the extraction function.

For example:
```
url: https://lightfinder.erco.com/specsheets/show/{art_no:s}/en/
```
then calling the extraction via:
```
extract_http.extract.extract(config, art_no="A2000292")
```
will result in `https://lightfinder.erco.com/specsheets/show/A2000292/en/` being requested.

This allows for an easy way to loop through a list of similar or related URLs.

## > params
Dictionary with any keys.

Parameters to be supplied as part of the HTTP Query String.
Supplying
```
url: https://lightfinder.erco.com/specsheets/show/{art_no:s}/en/
params:
    api: v1.1
```
is the equivalent of
```
url: https://lightfinder.erco.com/specsheets/show/{art_no:s}/en/?api=v1.1
```

If `file` is supplied, this is ignored.

## > file
Optional String.

Use a local path as the source instead of `url`.
If `file` is supplied, no HTTP requests will be made even if `url` is supplied.

If embed URL data (`locate[]` > `transform` > `embed`) is needed, `url` is still required so that the absolute URL can be found.


## > locate
Only valid when `type` is `html`.
Optional List of Dictionaries, each having the following structure:
[
- search_root : List of Strings, see below
- One of the following keys:
  - array : Dictionary, see below
  - lists : Dictionary, see below
  - values : Dictionary, see below
- [ transform : Dictionary, see below ]
]

Instructs extract_http to extract independent groups of data.

Returns a List containing a List of records for each item in `locate`.

## > locate[] > search_root
List of Strings or Dictionaries.

Defines a list of nodes to extract as data records.

Starting with the root node, instructs extract_http to iterate through each element of the list:
- if the element is a String:
  - uses `BeautifulSoup.select()` to select a list of nodes
- if the element is a Dictionary:
  - the Dictionary can contain the following keys:
    - args : Optional List
    - kwargs : Optional Dictionary
  - uses `BeautifulSoup.find_all(*args, **kwargs)` to select a list of nodes
    - where args and kwargs are elements of the supplied Dictionary.
The selected nodes are then passed to the next element of the list until the list is exhausted.

Each resultant node will be treated as a single record for the purpose of this `locate[]` element.

For more information about `BeautifulSoup.select()` and `BeautifulSoup.find_all(*args, **kwargs)`:
https://www.crummy.com/software/BeautifulSoup/bs4/doc/

## > locate[] > array
Dictionary with keys:
- key : String, in Format String syntax. See Format String section below.
- value : String, in Format String syntax. See Format String section below.

Extract a dictionary of values, of which the keys are defined by the nodes, as opposed to being pre-defined in the configuration.

This is most useful for a table of data:
```
<table class="employee_table">
    <tr>
        <td>Name</td>
        <td>John Doe</td>
    </tr>
    <tr>
        <td>Age</td>
        <td>35</td>
    </tr>
    <tr>
        <td>Email</td>
        <td>john.doe@sample.com</td>
    </tr>
</table>
```
By using the following as `locate[]`:
```
{
    "search_root": [
        "table.employee_table>tr"
    ],
    "array": {
        "key": "td#0",
        "value": "td#1",
    }
}
```
the following output will be returned:
```diff
[
+    {
+        "Name":"John Doe",
+        "Age":"35",
+        "Email":"john.doe@sample.com",
+    }
]
```

## > locate[] > values
Dictionary with any keys:
- [parameter_name] : String, in Format String syntax. See Format String section below.

(WIP)

## > locate[] > lists
Dictionary with any keys:
- [parameter_name] : String, in Format String syntax. See Format String section below.

Find all the nodes matching
(WIP)

## > locate[] > transform
Optional Dictionary with any keys:
- [parameter_name] : Dictionary with one or more of the following keys:
  - source : String, in Key String format, see below.
  - subsitute : Dictionary, see below
  - type : String, see below
  - embed : String, see below

[parameter_name] itself is a String in Key String format. See separate section below.

## > locate[] > transform > [parameter_name] > source
String, in Format String syntax. See Format String section below.

Defines where the information for `[parameter_name]` originates.

This string will be formatted (i.e. `source.format(**record)`) against the current record data. This allows new keys to be formed by concatenating and simple transformations of scaped data.

For example, if our record from `locate[]` currently contains:
```
{
    "Name":"John Doe",
    "Age":"35",
    "Email":"john.doe@sample.com",
}
```
Then having a `transform` of
```
"transform":{
    "padded_name":{
        "source":"[{Name:60s}]",
    }
    "description":{
        "source":"{Name} is an employee of age {Age}. Contact him at {Email}.",
    }
}
```
will result in:
```diff
{
    "Name":"John Doe",
    "Age":"35",
    "Email":"john.doe@sample.com",
+    "padded_name":"[John Doe                                                    ]",
+    "description":"John Doe is an employee of age 35. Contact him at john.doe@sample.com."
}
```

If this is not supplied and `[parameter_name]` already exists in the record, source will by default take the value of `{[parameter_name]}` as `source`.

Further transformations will be executed in the following order:
- `substitute`
- `embed`
- `type`

## > locate[] > transform > [parameter_name] > substitute
Dictionary with both of the following keys:
  - pattern : String
  - rep : String

Use a regular expression to transform the text from `source`.
(WIP)

## > locate[] > transform > [parameter_name] > type
String, One of the following values:
- int
- float
- str
- bytes

Transform the resultant text into the desired type.
For example, if our record from `locate[]` currently contains:
```
{
    "Name":"John Doe",
    "Age":"35",
    "Email":"john.doe@sample.com",
}
```
Then having a `transform` of
```
"transform":{
    "Age":{
        "type":"int"
    }
}
```
will result in:
```diff
{
    "Name":"John Doe",
!    "Age":35,
    "Email":"john.doe@sample.com",
}
```
Note that 35 is now an int.
`"type":"bytes"` is a special case - it encodes the String as UTF-8 bytes. However be mindful that bytes objects are not serialisable in JSON, avoid JSON is part of the workflow.

## > locate[] > transform > [parameter_name] > embed
String, One of the following values:
- url
Download and embed the HTTP resoure located at `source`.

Non-text formats will be embedded in base64.

## > transform
Only valid when `type` is `json`.

Optional Dictionary with any keys:
- [parameter_name] : Dictionary with one or more of the following keys:
  - source : String, in Key String format. See below.
  - subsitute : Dictionary
  - type : String
  - embed : String

Refer to `> locate[] > transform` above.




# Format Strings
Defines what to extract from the node.
Syntax:
```
BS4_SELECT_STRING[$(innerHTML|innerText|stripText|outerHTML|attr[ATTR_NAME])]
```

Typical Examples:
- `div.description>ul` (assumes innerHTML if not specified)
- `img.product-image$attr[src]`
- `div.access-download.access-manual>a$attr[href]`


# Key Strings
Defines the key of dictionary or sub-dictionaries to source or put the data.
Syntax:
```
DICT_KEY[>>>SUBDICT1_KEY[>>>SUBDICT2_KEY[>>>SUBDICT3_KEY[...]]]]
```

Key Strings allow transformations to be applied to nested dictionaries. This is most useful when `type` is `json` and the incoming data structure has multiple layers.

For example, if our data currently contains:
```
[
    {
        "Name":"John Doe",
        "Age":"35",
        "Email":"john.doe@sample.com",
        "Employment":{
            "Contract Type":"Permanent",
            "Role":"Backend Developer",
            "Salary":"40000",
        }
    },
    {
        "Name":"Jane Doe",
        "Age":"30",
        "Email":"jane.doe@sample.com",
        "Employment":{
            "Contract Type":"Contractor",
            "Role":"Data Engineer",
            "Salary":"52000",
        }
    },
]
```
Then having a `transform` of
```
"transform":{
    "Employment>>>Terms":{
        "source":"[{Name} shall be paid ${Employment>>>Salary:,d} annually for the {Employment>>Contract Type}Role of {Employment>>Role}.]",
    }
}
```
will result in:
```diff
[
    {
        "Name":"John Doe",
        "Age":"35",
        "Email":"john.doe@sample.com",
        "Employment":{
            "Contract Type":"Permanent",
            "Role":"Backend Developer",
            "Salary":"40000",
+            "Terms":"John Doe shall be paid $40,000 annually for the Permanent Role of Backend Developer.",
        }
    },
    {
        "Name":"Jane Doe",
        "Age":"30",
        "Email":"jane.doe@sample.com",
        "Employment":{
            "Contract Type":"Contractor",
            "Role":"Data Engineer",
            "Salary":"52000",
+            "Terms":"Jane Doe shall be paid $52,000 annually for the Contractor Role of Data Engineer.",
        }
    },
]
```