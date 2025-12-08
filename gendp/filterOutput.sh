#!/usr/bin/bash

rm -rf Traces
mkdir Traces

#!/usr/bin/bash

cp out.txt Traces/outFull.txt

rm -rf Traces
mkdir Traces

#strip out PE traces
for i in {0..3}; do
  grep -P "^PE\[${i}\].*@\d+:[0-9a-f]+" out.txt | grep -oP '@\d+:[0-9a-f]+'  > "Traces/pe${i}.txt"
  grep -P "^PE\[${i}\]" out.txt | paste -sd' \n' - > "Traces/fullPe${i}.txt"
done

#strip out main trace
grep -P "^main" out.txt | grep -oP '@\d+:[0-9a-f]+' | paste -sd' \n' - > Traces/main.txt
grep -P "^main" out.txt | paste -sd' \n' - > Traces/fullMain.txt

#strip out all traces. Just get raw output
grep -Pv "^PE\[\d\]|^main|^$" out.txt > Traces/out.txt
cp out.txt Traces/fullOut.txt



#input=$(cat)
#
##strip out PE traces
#for i in {0..3}; do
#  echo $input | grep -P "^PE\[${i}\]" | grep -oP '@\d+:[0-9a-f]+' | paste -sd' \n' - > "Traces/pe${i}.txt"
#  echo $input | grep -P "^PE\[${i}\]" | paste -sd' \n' - > "Traces/fullPe${i}.txt"
#done
##strip out main trace
#echo $input | grep -P "^main" | grep -oP '@\d+:[0-9a-f]+' | paste -sd' \n' - > Traces/main.txt
#echo $input | grep -P "^main" | paste -sd' \n' - > Traces/fullMain.txt
#
##strip out all traces. Just get raw output
#echo $input | grep -Pv "^PE\[\d\]|^main" > Traces/out.txt
#
#echo $input | grep -Pv "^PE\[\d\]|^main"


