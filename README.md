# python-pocsag

# Features:
- TX Batch, Single Preamble + "X"-repeat of "Y"-messages
- Supports inverted POCSAG
- Numeric and ASCII(7bit) supported


# Code:
POCSAG Encoder for Python

```python
from pocsag import encodeTXBatch
msgs = []
# Format = [ IsNumeric, Address(also supports A,B,C,D suffix like "133703C"), Message ]
msgs.append([False, "133702", 'PROBE Alarm - AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz.:;#!" 0123456789'])
data = encodeTXBatch(msgs) #, repeatNum = 2, inverted = False
```
