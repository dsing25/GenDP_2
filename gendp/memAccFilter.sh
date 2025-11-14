grep -Po "Move initiate ld SPM\[\d+\] to [^\.]+|recv SPM: [^=]+= \d+|Move \d+ from.* to SPM\[\d+\]" Traces/fullPe0.txt  > pe0SpmAccesses.txt
grep -Po "Move \d+ from SPM\[\d+\] to [^.]+|Move \d+ from .*to SPM\[\d+\]" ../../gendpdev2/gendp/Traces/fullPe0.txt > truePe0SpmAccesses.txt
