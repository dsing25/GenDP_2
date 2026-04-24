#!/usr/bin/env python3
"""
Dump per-query SPM footprint sizes (bytes) from graph.soa.

Mirrors gssw_sim.cpp:gssw_spm_size() exactly.

Usage:
  python3 scripts/gssw_dump_query_sizes.py [-i <graph.soa>] [-o <out>]
Defaults:
  -i /data4/kaplannp/GenDP2/kernel/Gssw/Dataset/graph.soa
  -o /data4/kaplannp/GenDP2/kernel/Gssw/Dataset/querySizes.txt
Output format (TSV):
  index\tsize_bytes\tnum_nodes\ttotal_nexts\ttotal_seq
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
KERNEL_DIR = Path('/data4/kaplannp/GenDP2/kernel/Gssw')
DEFAULT_IN = KERNEL_DIR / 'Dataset' / 'graph.soa'
DEFAULT_OUT = KERNEL_DIR / 'Dataset' / 'querySizes.txt'

# Constants from gssw_sim.cpp (must stay in sync)
GSSW_SEG_LEN = 19
GSSW_VEC_WORDS = 2
GSSW_SPM_PAD = 8

GSSW_HPING_OFF = 4 * GSSW_SEG_LEN * 8                     # 608
GSSW_HPONG_OFF = GSSW_HPING_OFF + GSSW_SEG_LEN * 8        # 760
GSSW_E_OFF     = GSSW_HPONG_OFF + GSSW_SEG_LEN * 8        # 912
GSSW_F_OFF     = GSSW_E_OFF    + GSSW_SEG_LEN * 8 + GSSW_SPM_PAD  # 1072
GSSW_BEST_OFF  = GSSW_F_OFF    + GSSW_SEG_LEN * 8 + GSSW_SPM_PAD  # 1232
GSSW_GRAPH_OFF = GSSW_BEST_OFF + GSSW_SEG_LEN * 8         # 1384

SIZEOF_SPM_GRAPH_META = 16                                # 4 uint32
SIZEOF_SPM_NODE_DESC  = 8 + GSSW_SEG_LEN * GSSW_VEC_WORDS * 4 * 2  # 312


def spm_size(num_nodes, total_nexts, total_seq):
    sz = GSSW_GRAPH_OFF
    sz += SIZEOF_SPM_GRAPH_META
    sz += num_nodes * SIZEOF_SPM_NODE_DESC
    nexts_bytes = total_nexts * 2
    nexts_bytes = (nexts_bytes + 3) & ~3  # align to 4 bytes
    sz += nexts_bytes
    # Sequence packed 2-bit: 16 bases per 32-bit word
    sz += ((total_seq + 15) // 16) * 4
    return sz


def parse_args():
    inp = DEFAULT_IN
    outp = DEFAULT_OUT
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '-i' and i + 1 < len(args):
            inp = Path(args[i + 1]); i += 2
        elif args[i] == '-o' and i + 1 < len(args):
            outp = Path(args[i + 1]); i += 2
        else:
            print(f"Unknown arg: {args[i]}")
            sys.exit(1)
    return inp, outp


def main():
    inp, outp = parse_args()
    if not inp.exists():
        print(f"ERROR: {inp} not found")
        sys.exit(1)

    with open(inp) as fin, open(outp, 'w') as fout:
        header_count = int(fin.readline().strip())
        fout.write("index\tsize_bytes\tnum_nodes\ttotal_nexts\ttotal_seq\n")
        idx = 0
        while True:
            line1 = fin.readline()
            if not line1:
                break
            # Skip the 3 other lines of this entry
            fin.readline(); fin.readline(); fin.readline()
            parts = line1.split()
            num_nodes = int(parts[0])
            total_nexts = int(parts[1])
            total_seq = int(parts[2])
            sz = spm_size(num_nodes, total_nexts, total_seq)
            fout.write(f"{idx}\t{sz}\t{num_nodes}\t{total_nexts}\t{total_seq}\n")
            idx += 1

    print(f"Wrote {idx} entries to {outp}")
    if idx != header_count:
        print(f"WARNING: header said {header_count} queries, read {idx}")


if __name__ == '__main__':
    main()
