# python-pocsag
POCSAG Encoder for Python

```python
from pocsag import encodeTXBatch
msgs = []
msgs.append([False, "133702", 'PROBE Alarm - AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz.:;#!" 0123456789'])
data = encodeTXBatch(msgs)
```
