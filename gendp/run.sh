export PATTERN_WFA="GTTTAAAAGGTTTAAAAGGTTTAAAAGGTTTAAAAGGTT"
export TEXT_WFA="GAAAAAAATGAAAAAAATGAAAAAAATGAAAAAAATGAA"
python scripts/wfa_instruction_generator.py && make clean && make -j && ./sim -k 5 -i ../../kernel/Datasets/crossBlockSeq.seq -o wfaOneSeqOutput.txt -s -n -1 
