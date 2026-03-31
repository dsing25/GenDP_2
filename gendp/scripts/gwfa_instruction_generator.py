import os
from utils import *
from opcodes import *

LAST_SPM_ADDR = 32767

# PE code locations
PE_BUF0_COMPUTE = 1
PE_BUF0_SORT    = 5
PE_BUF1_COMPUTE = 9
PE_BUF1_SORT    = 13
PE_P2_BUF0      = 17
PE_P2_BUF1      = 21

# Magic IDs with mask encoding: (magic_id << 8) | mask
# mask bit 0 = buffer index (0=buf0, 1=buf1)
MAGIC_7_BUF0  = 7
MAGIC_7_BUF1  = (7 << 8) | 1
MAGIC_8_BUF0  = 8
MAGIC_8_BUF1  = (8 << 8) | 1
MAGIC_9_BUF0  = 9
MAGIC_9_BUF1  = (9 << 8) | 1
MAGIC_11_BUF0 = 11
MAGIC_11_BUF1 = (11 << 8) | 1
MAGIC_13_BUF0 = 13
MAGIC_13_BUF1 = (13 << 8) | 1
MAGIC_14_BUF0 = 14
MAGIC_14_BUF1 = (14 << 8) | 1
MAGIC_15_BUF0 = 15
MAGIC_15_BUF1 = (15 << 8) | 1

# Sort phase magic IDs
MAGIC_18_BUF0 = 18
MAGIC_18_BUF1 = (18 << 8) | 1
MAGIC_19      = 19
MAGIC_24_BUF0 = 24
MAGIC_24_BUF1 = (24 << 8) | 1
MAGIC_25_BUF0 = 25
MAGIC_25_BUF1 = (25 << 8) | 1
MAGIC_32      = 32

# PE sort code locations
PE_SORT_BIN_COUNT_PING = 25
PE_SORT_BIN_COUNT_PONG = 29
PE_SORT_SCATTER_PING   = 33
PE_SORT_SCATTER_PONG   = 37

# PE magic IDs for sort
MAGIC_20_BUF0 = 20
MAGIC_20_BUF1 = (20 << 8) | 1
MAGIC_21_BUF0 = 21
MAGIC_21_BUF1 = (21 << 8) | 1

# Intv merge magic ID
MAGIC_26      = 26

# Dedup phase magic IDs (ctrl)
MAGIC_29      = 29
MAGIC_30_BUF0 = 30
MAGIC_30_BUF1 = (30 << 8) | 1
MAGIC_31_BUF0 = 31
MAGIC_31_BUF1 = (31 << 8) | 1
MAGIC_32      = 32

# PE dedup code locations
PE_DEDUP_PING = 41
PE_DEDUP_PONG = 45

# PE magic IDs for dedup
MAGIC_23_BUF0 = 23
MAGIC_23_BUF1 = (23 << 8) | 1

def emit_sort_loop(f):
    """Emit one radix sort pass loop (42 instructions). Position-independent.
    Caller must set gr[1]=0 before calling. Uses gr[1..7,24], s1c[], SPM."""
    # --- BIN COUNT PHASE ---
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # +0: gr[2]=0 (cursor=0)
    f.write(write_magic(MAGIC_18_BUF0))                                                            # +1: load tile→PING
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PING, 0, 0, 0, 0, 0, set_PC)) # +2: set_PC bin count PING
    f.write(data_movement_instruction(0, 0, 0, 0, 12, 0, 1, 0, 2, 6, bge))                      # +3: bge cursor>=nape → +12 (+15)
    f.write(write_magic(MAGIC_18_BUF1))                                                            # +4: SS_PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +5: spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PONG, 0, 0, 0, 0, 0, set_PC)) # +6: set_PC bin count PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 1, 0, 2, 6, bge))                       # +7: bge → +6 (+13)
    f.write(write_magic(MAGIC_18_BUF0))                                                            # +8: SS_PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +9: spin
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_BIN_COUNT_PING, 0, 0, 0, 0, 0, set_PC)) # +10: set_PC bin count PING
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 1, 0, 2, 6, bge))                       # +11: bge → +4 (+15)
    f.write(data_movement_instruction(0, 0, 0, 0, -8, 0, 0, 0, 0, 0, jump))                      # +12: jump -8 (+4: SS_PONG)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +13: EPIL_B: spin
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # +14: jump +2 (+16)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +15: EPIL_A: spin
    f.write(write_magic(MAGIC_19))                                                                  # +16: prefix sum
    # --- SCATTER PHASE ---
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # +17: gr[2]=0
    f.write(write_magic(MAGIC_24_BUF0))                                                            # +18: load tile→PING
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PING, 0, 0, 0, 0, 0, set_PC))  # +19: set_PC scatter PING
    f.write(data_movement_instruction(0, 0, 0, 0, 15, 0, 1, 0, 2, 6, bge))                      # +20: bge → +15 (+35)
    f.write(write_magic(MAGIC_24_BUF1))                                                            # +21: SS_PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +22: spin
    f.write(write_magic(MAGIC_25_BUF0))                                                            # +23: writeback PING
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PONG, 0, 0, 0, 0, 0, set_PC))  # +24: set_PC scatter PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 1, 0, 2, 6, bge))                       # +25: bge → +7 (+32)
    f.write(write_magic(MAGIC_24_BUF0))                                                            # +26: SS_PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +27: spin
    f.write(write_magic(MAGIC_25_BUF1))                                                            # +28: writeback PONG
    f.write(data_movement_instruction(0, 0, 0, 0, PE_SORT_SCATTER_PING, 0, 0, 0, 0, 0, set_PC))  # +29: set_PC scatter PING
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 1, 0, 2, 6, bge))                       # +30: bge → +5 (+35)
    f.write(data_movement_instruction(0, 0, 0, 0, -10, 0, 0, 0, 0, 0, jump))                     # +31: jump -10 (+21: SS_PONG)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +32: SEPIL_B: spin
    f.write(write_magic(MAGIC_25_BUF1))                                                            # +33: writeback PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, 0, 0, jump))                       # +34: jump +3 (+37)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # +35: SEPIL_A: spin
    f.write(write_magic(MAGIC_25_BUF0))                                                            # +36: writeback PING
    # --- PASS FOOTER ---
    f.write(data_movement_instruction(gr, gr, 0, 0, 7, 0, 0, 0, 3, 0, mv))                      # +37: gr[7]=gr[3] (swap)
    f.write(data_movement_instruction(gr, gr, 0, 0, 3, 0, 0, 0, 4, 0, mv))                      # +38: gr[3]=gr[4]
    f.write(data_movement_instruction(gr, gr, 0, 0, 4, 0, 0, 0, 7, 0, mv))                      # +39: gr[4]=gr[7]
    f.write(data_movement_instruction(gr, gr, 0, 0, 1, 0, 0, 0, 1, 1, addi))                    # +40: gr[1]++
    f.write(data_movement_instruction(0, 0, 0, 0, -41, 0, 0, 0, 8, 1, bne))                     # +41: bne 8!=gr[1] → -41 (+0)

def gwfa_main_instruction():
    f = InstructionWriter("instructions/gwfa/main_instruction.txt")
    f.write(write_magic(1))                                                                        # PC 0: init
    f.write(data_movement_instruction(SPM, gr, 0, 0, LAST_SPM_ADDR, 0, 0, 0, 0, 0, mv))          # PC 1: SPM[32767]=0
    # === STEP LOOP ===
    f.write(write_magic(4))                                                                        # PC 2: begin_step
    f.write(data_movement_instruction(gr, 0, 0, 0, 14, 0, 0, 0, 0, 0, si))                       # PC 3: gr[14]=0 (cursor)
    # === PHASE 1 PROLOGUE (buf0, no prev writeback) ===
    f.write(write_magic(MAGIC_7_BUF0))                                                             # PC 4: tile_load buf0
    f.write(write_magic(MAGIC_8_BUF0))                                                             # PC 5: load_seq_info buf0
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 6: set_PC buf0 compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 7: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 8: set_PC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 9: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 17, 0, 1, 0, 14, 15, bge))                     # PC 10: bge cursor>=n_a → +17 (PC 27: P1_EPIL_A)
    # === PHASE 1 STEADY STATE: buf1 half ===
    # Load+compute buf1, writeback buf0 during compute
    f.write(write_magic(MAGIC_7_BUF1))                                                             # PC 11: tile_load buf1
    f.write(write_magic(MAGIC_8_BUF1))                                                             # PC 12: load_seq_info buf1
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 13: set_PC buf1 compute
    f.write(write_magic(MAGIC_9_BUF0))                                                             # PC 14: writeback buf0 ← overlaps PE compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 15: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF1_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 16: set_PC buf1 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 17: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 1, 0, 14, 15, bge))                     # PC 18: bge cursor>=n_a → +11 (PC 29: P1_EPIL_B)
    # === PHASE 1 STEADY STATE: buf0 half ===
    # Load+compute buf0, writeback buf1 during compute
    f.write(write_magic(MAGIC_7_BUF0))                                                             # PC 19: tile_load buf0
    f.write(write_magic(MAGIC_8_BUF0))                                                             # PC 20: load_seq_info buf0
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_COMPUTE, 0, 0, 0, 0, 0, set_PC))       # PC 21: set_PC buf0 compute
    f.write(write_magic(MAGIC_9_BUF1))                                                             # PC 22: writeback buf1 ← overlaps PE compute
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 23: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, PE_BUF0_SORT, 0, 0, 0, 0, 0, set_PC))          # PC 24: set_PC buf0 sort
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 25: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, -15, 0, 1, 0, 14, 15, blt))                    # PC 26: blt cursor<n_a → -15 (PC 11: SS buf1)
    # fallthrough: cursor >= n_a → P1_EPIL_A
    # === P1 EPILOGUE A: writeback buf0 ===
    f.write(write_magic(MAGIC_9_BUF0))                                                             # PC 27: writeback buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # PC 28: jump +2 → PC 30 (FIFO_FLUSH)
    # === P1 EPILOGUE B: writeback buf1 ===
    f.write(write_magic(MAGIC_9_BUF1))                                                             # PC 29: writeback buf1
    # fallthrough to FIFO_FLUSH
    # === FIFO FLUSH (guarded by gr[2] from magic 9) ===
    f.write(data_movement_instruction(0, 0, 0, 0, 4, 0, 0, 0, 0, 2, beq))                        # PC 30: beq gr[2]==0 → +4 (PC 34: P2 prologue)
    f.write(data_movement_instruction(gr, fifo[0], 0, 0, 3, 0, 0, 0, 0, 0, mv))                  # PC 31: gr[3]=fifo[0]
    f.write(data_movement_instruction(gr, fifo[1], 0, 0, 4, 0, 0, 0, 0, 0, mv))                  # PC 32: gr[4]=fifo[1]
    f.write(write_magic(12))                                                                       # PC 33: flush to s_B_a
    # === PHASE 2 PROLOGUE (bufA, no prev writeback) ===
    f.write(write_magic(MAGIC_14_BUF0))                                                            # PC 34: p2 tile load bufA
    f.write(data_movement_instruction(0, 0, 0, 0, 20, 0, 0, 0, 0, 2, beq))                       # PC 35: beq gr[2]==0 → +20 (PC 55: P2_FINAL)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))            # PC 36: set_PC p2 bufA
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 37: spin gr[13]
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 38: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 137, 0, 0, 0, 0, 1, bne))                      # PC 39: bne gr[1]!=0 -> +137 (PC 176: SCORE)
    # === PHASE 2 STEADY STATE: bufB half ===
    # Writeback bufA FIRST (pushes to A queue), then load+compute bufB
    f.write(write_magic(MAGIC_15_BUF0))                                                            # PC 40: writeback bufA → A queue
    f.write(write_magic(MAGIC_14_BUF1))                                                            # PC 41: p2 tile load bufB
    f.write(data_movement_instruction(0, 0, 0, 0, 13, 0, 0, 0, 0, 2, beq))                       # PC 42: beq gr[2]==0 → +13 (PC 55: P2_FINAL)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF1, 0, 0, 0, 0, 0, set_PC))            # PC 43: set_PC p2 bufB
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 44: spin gr[13]
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 45: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 130, 0, 0, 0, 0, 1, bne))                      # PC 46: bne gr[1]!=0 -> +130 (PC 176: SCORE)
    # === PHASE 2 STEADY STATE: bufA half ===
    # Writeback bufB FIRST (pushes to A queue), then load+compute bufA
    f.write(write_magic(MAGIC_15_BUF1))                                                            # PC 47: writeback bufB → A queue
    f.write(write_magic(MAGIC_14_BUF0))                                                            # PC 48: p2 tile load bufA
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 0, 0, 0, 2, beq))                        # PC 49: beq gr[2]==0 → +6 (PC 55: P2_FINAL)
    f.write(data_movement_instruction(0, 0, 0, 0, PE_P2_BUF0, 0, 0, 0, 0, 0, set_PC))            # PC 50: set_PC p2 bufA
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 51: spin gr[13]
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 52: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 123, 0, 0, 0, 0, 1, bne))                      # PC 53: bne gr[1]!=0 -> +123 (PC 176: SCORE)
    f.write(data_movement_instruction(0, 0, 0, 0, -14, 0, 0, 0, 0, 0, jump))                     # PC 54: jump -14 → PC 40 (P2_SS_BUFB)
    # === PHASE 2 DONE → INTV SORT → INTV MERGE → DIAG SORT → DEDUP ===
    # magic 16: sync counters, filter next_intv, setup intv sort state
    f.write(write_magic(16))                                                                       # PC 55: P2_FINAL: intv sort setup
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                       # PC 56: gr[1]=0 (pass=0)
    # === SORT LOOP 1: intv sort (PCs 57-98, 42 instructions) ===
    emit_sort_loop(f)
    # === INTV MERGE + DIAG SORT SETUP ===
    f.write(write_magic(MAGIC_26))                                                                  # PC 99: intv merge + diag sort setup
    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 0, 0, si))                       # PC 100: gr[1]=0 (pass=0)
    # === SORT LOOP 2: diag sort (PCs 101-142, 42 instructions) ===
    emit_sort_loop(f)
    # === DEDUP LOOP ===
    f.write(write_magic(MAGIC_29))                                                                  # PC 143: split search + intv preload
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                       # PC 144: gr[2]=0 (dedup cursor)
    # --- DEDUP PROLOGUE: load PING tile ---
    f.write(write_magic(MAGIC_30_BUF0))                                                            # PC 145: load tile->PING, gr[2]+=DEDUP_TILE
    f.write(data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PING, 0, 0, 0, 0, 0, set_PC))         # PC 146: set_PC PE dedup PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 147: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 17, 0, 1, 0, 2, 6, bge))                      # PC 148: bge cursor>=niter -> +17 (PC 165: DEPIL_A)
    # --- SS_PONG: load PONG, spin for PING, writeback PING ---
    f.write(write_magic(MAGIC_30_BUF1))                                                            # PC 149: SS_PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 150: spin gr[13]
    f.write(write_magic(MAGIC_31_BUF0))                                                            # PC 151: writeback PING
    f.write(data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PONG, 0, 0, 0, 0, 0, set_PC))         # PC 152: set_PC PE dedup PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 153: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 6, bge))                       # PC 154: bge cursor>=niter -> +8 (PC 162: DEPIL_B)
    # --- SS_PING: load PING, spin for PONG, writeback PONG ---
    f.write(write_magic(MAGIC_30_BUF0))                                                            # PC 155: SS_PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 156: spin gr[13]
    f.write(write_magic(MAGIC_31_BUF1))                                                            # PC 157: writeback PONG
    f.write(data_movement_instruction(0, 0, 0, 0, PE_DEDUP_PING, 0, 0, 0, 0, 0, set_PC))         # PC 158: set_PC PE dedup PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 159: spin gr[13]
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 1, 0, 2, 6, bge))                       # PC 160: bge cursor>=niter -> +5 (PC 165: DEPIL_A)
    f.write(data_movement_instruction(0, 0, 0, 0, -12, 0, 0, 0, 0, 0, jump))                     # PC 161: jump -12 -> PC 149 (SS_PONG)
    # --- DEPIL_B: last PONG tile ---
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 162: DEPIL_B: spin gr[13]
    f.write(write_magic(MAGIC_31_BUF1))                                                            # PC 163: writeback last PONG output
    f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 0, 0, 0, 0, jump))                       # PC 164: jump +3 -> PC 167 (DEDUP_DONE)
    # --- DEPIL_A: last PING tile ---
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 1, 13, bne))                       # PC 165: DEPIL_A: spin gr[13]
    f.write(write_magic(MAGIC_31_BUF0))                                                            # PC 166: writeback last PING output
    # fallthrough to DEDUP_DONE
    f.write(write_magic(MAGIC_32))                                                                  # PC 167: DEDUP_DONE: gather + finalize
    # === STEP DONE ===
    f.write(data_movement_instruction(gr_lo, gr_lo, 0, 0, 12, 0, 0, 0, 1, 12, addi))             # PC 168: gr_lo[12]++ (s++)
    f.write(write_magic(5))                                                                        # PC 169: debug
    f.write(data_movement_instruction(gr, SPM, 0, 0, 1, 0, 0, 0, LAST_SPM_ADDR, 0, mv))          # PC 170: gr[1]=SPM[32767]
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 0, 0, 0, 1, bne))                        # PC 171: bne gr[1]!=0 -> +5 (PC 176: SCORE)
    f.write(data_movement_instruction(gr, gr_hi, 0, 0, 5, 0, 0, 0, 12, 0, mv))                   # PC 172: gr[5]=gr_hi[12] (s_term)
    f.write(data_movement_instruction(gr, gr_lo, 0, 0, 6, 0, 0, 0, 12, 0, mv))                   # PC 173: gr[6]=gr_lo[12] (s)
    f.write(data_movement_instruction(0, 0, 0, 0, -172, 0, 1, 0, 5, 6, bge))                     # PC 174: bge s_term>=s -> -172 (PC 2: STEP_LOOP)
    f.write(data_movement_instruction(0, 0, 0, 0, 2, 0, 0, 0, 0, 0, jump))                       # PC 175: jump +2 -> PC 177 (PRINT_SCORE)
    # === FINISH ===
    f.write(write_magic(17))                                                                       # PC 176: SCORE: set score
    f.write(write_magic(3))                                                                        # PC 177: PRINT_SCORE: print score
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # PC 178: halt
    f.close()

def gwfa_compute():
    f = InstructionWriter("instructions/gwfa/compute_instruction.txt")
    f.close()

def pe_instruction(pe_id):
    f = InstructionWriter("instructions/gwfa/pe_{}_instruction.txt".format(pe_id))
    # PC 0: halt -- wait for controller
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- BUF0: phase 1 compute + boundary sort ---
    # PC 1: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 2: compute buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_8_BUF0))                                                             # slot1: magic(8, mask=0)
    # PC 3: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 4: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 5: clear sync (sort)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 6: boundary sort buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_11_BUF0))                                                            # slot1: magic(11, mask=0)
    # PC 7: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 8: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- BUF1: phase 1 compute + boundary sort ---
    # PC 9: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 10: compute buf1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_8_BUF1))                                                             # slot1: magic(8, mask=1)
    # PC 11: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 12: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # PC 13: clear sync (sort)
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 14: boundary sort buf1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_11_BUF1))                                                            # slot1: magic(11, mask=1)
    # PC 15: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 16: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Phase 2 buf0 ---
    # PC 17: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 18: phase 2 compute buf0
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_13_BUF0))                                                            # slot1: magic(13, mask=0)
    # PC 19: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 20: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Phase 2 buf1 ---
    # PC 21: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 22: phase 2 compute buf1
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_13_BUF1))                                                            # slot1: magic(13, mask=1)
    # PC 23: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 24: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort bin count PING (PE_SORT_BIN_COUNT_PING = 25) ---
    # PC 25: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 26: bin count PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_20_BUF0))                                                            # slot1: magic(20, mask=0)
    # PC 27: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 28: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort bin count PONG (PE_SORT_BIN_COUNT_PONG = 29) ---
    # PC 29: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 30: bin count PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_20_BUF1))                                                            # slot1: magic(20, mask=1)
    # PC 31: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 32: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort scatter PING (PE_SORT_SCATTER_PING = 33) ---
    # PC 33: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 34: scatter PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_21_BUF0))                                                            # slot1: magic(21, mask=0)
    # PC 35: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 36: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Sort scatter PONG (PE_SORT_SCATTER_PONG = 37) ---
    # PC 37: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 38: scatter PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_21_BUF1))                                                            # slot1: magic(21, mask=1)
    # PC 39: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 40: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Dedup PING (PE_DEDUP_PING = 41) ---
    # PC 41: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 42: dedup PING
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_23_BUF0))                                                            # slot1: magic(23, mask=0)
    # PC 43: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 44: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    # --- Dedup PONG (PE_DEDUP_PONG = 45) ---
    # PC 45: clear sync
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 0, 0, si))                       # slot1: gr[10]=0
    # PC 46: dedup PONG
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(write_magic(MAGIC_23_BUF1))                                                            # slot1: magic(23, mask=1)
    # PC 47: signal done
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, none))                       # slot0: nop
    f.write(data_movement_instruction(gr, 0, 0, 0, 10, 0, 0, 0, 1, 0, si))                       # slot1: gr[10]=1
    # PC 48: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot0: halt
    f.write(data_movement_instruction(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, halt))                       # slot1: halt
    f.close()

if not os.path.exists("instructions/gwfa"):
    os.makedirs("instructions/gwfa")
gwfa_compute()
gwfa_main_instruction()
pe_instruction(0)
pe_instruction(1)
pe_instruction(2)
pe_instruction(3)
