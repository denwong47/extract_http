# extract_http
 Web Scraping through configuration dictionaries


## extract_http.extract.extract

Extract information from a HTML or JSON API as according to a configuration dictionary.
```
def bounds_of_nth_prime(
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
String.

## > url
String.

## > params
Dictionary with any keys.

## > locate
List of Dictionaries, each having the following structure:
[
- search_root : List of Strings, see below
- One of the following keys:
  - array : Dictionary, see below
  - lists : Dictionary, see below
  - values : Dictionary, see below
- [ transform : Dictionary, see below ]
]

## > locate[] > search_root
List of Strings.

## > locate[] > array
Dictionary with keys:
- key : String
- value : String

## > locate[] > lists
Dictionary with any keys:
- [parameter_name] : List of Strings, or String

## > locate[] > values
Dictionary with any keys:
- [parameter_name] : List of Strings, or String

## > locate[] > transform
Optional Dictionary with any keys:
- [parameter_name] : Dictionary with one or more of the following keys:
  - source : String, see below
  - subsitute : Dictionary, see below
  - type : String, see below
  - embed : String, see below

## > locate[] > transform > source
String

## > locate[] > transform > subsitute
Dictionary with both of the following keys:
  - pattern : String
  - rep : String

## > locate[] > transform > type
String
One of the following values:
- int
- float
- str
- bytes

## > locate[] > transform > embed
String
One of the following values:
- url