# High Level
I want to enable SPM pipelining, so the following should be legal
```
insX
a = ld SPM

insX
b = ld SPM

use of a
insY

use of b
insZ
```
but if insY was use of b it would still be illegal because latency is preserved
# Details
Currently we can only have one inflight SPM request per bank. Instead, I want to pipeline SPM so it
has two stages, and I can have two inflight request from the same or different pes in flight at the
same time.
