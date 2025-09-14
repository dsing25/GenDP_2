def bswdev_comp():

    f.write(compute_instruction(sub, beq, mv, i, qlen, 0, 0, 0, 0, head))        # head = max(0, i-qlen)
    # find start of the band (head)
    f.write(compute_instruction(add, beq, add_8, qlen, qlen, 0, 0, tlen, 0, mlen))   # mlen = min(qlen+qlen, tlen)
    # find the band width mlen 
    f.write(compute_instruction(set_PC, halt, beq, head, tlen, 0, exit0, 0, 0, exit0)) # exit0 = head > tail ? 0 : 1
    # exit if band is invalid (head > tail)
    f.write(compute_instruction(set_PC, halt, beq, mismatch, qlen, mlen, tlen, 0, 0, mlen)) # mlen = 64 > qlen ? mlen : tlen
    # adjusts mlen based on the query length
    f.write(compute_instruction(set_PC, halt, beq, i, mlen, 0, exit0, 0, 0, exit0))  # exit0 = i > mlen ? 0 : exit0
    # update exit condition based on index and band width
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))      # halt
    # no op
    f.write(compute_instruction(none, halt, beq, head, tlen, 0, exit0, 0, 0, exit0)) # exit0 = head == tail ? 0 : exit0
    # update exit condition again if band is single column
    f.write(compute_instruction(beq, halt, beq, 0, 0, 0, 0, 0, 0, E_up))     # E_up = 0
    # initialize gap extension score
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))      # halt
    # no op
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))      # halt
    # no op

    # ask about what the opcode 16 does?

    f.write(compute_instruction(bge, beq, add, target_i, query_j, 0, 0, H_diag, 0, tmp))      # S = match_score(query, ref) + H_diag
    # this calculates the match/mismatch scores and adds the diagonal score
    f.write(compute_instruction(set_PC, halt, beq, tlen, i, exit0, 0, 0, 0, exit0))           # exit0 = tlen > i ? exit0 : 0
    # exit condition - checks if current row is within tlen
    f.write(compute_instruction(set_PC, add, add, H_diag, 0, tmp, 0, gap_o, gap_e, tmp2))     # H_diag = H_diag > 0 ? H_diag_S : 0; tmp = H_diag - (gap_o + gap_e)
    # update h diag and calculates gap penalties
    f.write(compute_instruction(set_PC, mv, mv, H_diag, 0, tmp, 0, F_left, E_up, H))          # H_diag = H_diag > 0 ? H_diag_S : 0; H = F_left > E_up ? F_left : E_up; H = H > H_diag ? H : H_diag
    # computes cell score and updates h diag
    f.write(compute_instruction(set_PC, halt, beq, 0, j, H_left, H, 0, 0, H_left))            # H_left = 0 > j ? H_left : H
    # updates h_left, first column keeps h_left or else becomes H
    f.write(compute_instruction(mv, add, mv, tmp2, 0, 0, 0, E_up, gap_e, E_up))               # E_up -= gap_e; tmp = tmp > 0? tmp : 0; E = E_up > tmp? E_up : tmp
    # update E_up for next cell. gap extension penalty
    f.write(compute_instruction(mv, add, mv, tmp2, 0, 0, 0, F_left, gap_e, F_left))           # F_left -= gap_e; tmp = tmp > 0? tmp : 0; F = F_left > tmp? F_left : tmp
    # updates F left. horizontal gap score
    f.write(compute_instruction(set_PC, halt, beq, max_H, H, m_j, j, 0, 0, m_j))              # m_j = max_H > H? m_j : j
    # update m_j. maximum score coverage
    f.write(compute_instruction(set_PC, halt, beq, max_H, H, max_H, H, 0, 0, max_H))          # max_H = max_H > H? max_H : H
    f.write(compute_instruction(add, halt, beq, j, max_H, 0, 0, 0, 0, j))                     # j++
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                       # halt
    f.write(compute_instruction(set_PC, halt, beq, F_left, j, 0, F_left, 0, 0, F_left))       # F = 1 > j ? 0 : F


    f.write(compute_instruction(none, halt, beq, j, qlen, one, 0, 0, 0, mlen))      # cmp1 = (j == qlen) ? 1 : 0
    # detects the end of the query sequence in band
    f.write(compute_instruction(set_PC, halt, beq, gscore, H, max_ie, i, 0, 0, tmp))    # max_ie_new = (gscore > H_left) ? max_ie : i
    # tracks row index for best alignment
    f.write(compute_instruction(set_PC, halt, beq, exit0, 0, mlen, 0, 0, 0, mlen))     # cmp1 = (exit0 > 0) ? cmp1 : 0
    # propagates exit condition through the band
    f.write(compute_instruction(set_PC, halt, beq, gscore, H, gscore, H, 0, 0, head))  # gscore = (gscore > H_left) ? gscore : H_left
    # updates the best score at band start
    f.write(compute_instruction(set_PC, halt, beq, mlen, 0, tmp, max_ie, 0, 0, max_ie))# max_ie = (cmp1 > 0) ? max_ie_new : max_ie
    # finalize alignment index if band condition is met
    f.write(compute_instruction(set_PC, halt, beq, mlen, 0, head, gscore, 0, 0, gscore))# gscore = (cmp1 > 0) ? gscore_new : gscore
    # finalize the best score if band cond is met
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))               # halt
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))               # halt


    f.write(compute_instruction(none, halt, beq, m, 0, one, 0, 0, 0, mlen))       # tmp = m == 0 ? 1 : 0
    # detect if alignment is empty based on max score
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))               # halt
    f.write(compute_instruction(none, halt, beq, mlen, one, 0, one, 0, 0, head))       # break0 = tmp == 1 ? 0 : 1
    # finds a break in alignment
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))               # halt
    f.write(compute_instruction(set_PC, halt, beq, mlen, 0, 0, exit0, 0, 0, exit0))    # exit0 = tmp > 0 ? 0 : exit0
    # update exit conditions
    f.write(compute_instruction(beq, halt, beq, max, 0, 0, 0, 0, 0, head))             # old_max_score = max_score
    # finds new maximum
    f.write(compute_instruction(mv, halt, beq, m, max, 0, 0, 0, 0, mlen))          # tmp_max = max(m, max_score)
    # best score for current row
    f.write(compute_instruction(sub, halt, beq, i, m_j, 0, 0, 0, 0, tmp))              # diff = m_j - i
    # calculate offset for alignment endpoint
    f.write(compute_instruction(set_PC, halt, beq, exit0, 0, mlen, max, 0, 0, max))    # max_score = exit0 > 0 ? tmp_max : max_score
    # best score is only updated if band is valid
    f.write(compute_instruction(sub, halt, beq, m_j, i, 0, 0, 0, 0, tmp2))             # diff_minus = i - m_j
    # finds offset and alignment endpoints 
    f.write(compute_instruction(set_PC, halt, beq, max, head, one, 0, 0, 0, mlen))     # cmp = max_score > old_max_score ? 1 : 0
    # score comparison to find new best alignment
    f.write(compute_instruction(set_PC, halt, beq, tmp, 0, tmp, tmp2, 0, 0, tmp3))     # max_off_new = diff > 0 ? diff : diff_minus
    # maximum offset for alignment
    f.write(compute_instruction(set_PC, halt, beq, mlen, 0, m_j, qle, 0, 0, qle))      # qle = cmp > 0 ? m_j : qle
    # updates query index if new alignment found
    f.write(compute_instruction(mv, halt, beq, tmp3, max_off, 0, 0, 0, 0, tmp3))       # max_off_new = max(max_off_new, max_off)
    # reported offset is the largest one found
    f.write(compute_instruction(set_PC, halt, beq, mlen, 0, i, tle, 0, 0, tle))        # tle = cmp > 0 ? i : tle
    # updates index with new best alignment
    f.write(compute_instruction(set_PC, halt, beq, mlen, 0, tmp3, max_off, 0, 0, max_off)) # max_off = cmp > 0 ? max_off_new : max_off
    # finalizes maximum offset for alignment
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))               # halt
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))               # halt


    f.write(compute_instruction(set_PC, halt, beq, max_score_pre, max_score, one, 0, 0, 0, cmp))     # cmp = max_score_pre > max_score ? 1 : 0
    # finds the best global score using multiple merged bands
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                             # halt
    f.write(compute_instruction(set_PC, halt, beq, cmp, 0, max_score_pre, max_score, 0, 0, max_score))    # max_score = cmp > 0 ? max_score_pre : max_score
    # ensures final score is the best
    f.write(compute_instruction(set_PC, halt, beq, gscore_pre, gscore, max_ie_pre, max_ie, 0, 0, max_ie)) # max_ie = gscore_pre > gscore ? max_ie_pre : max_ie
    # tracks index for best alignment across bands
    f.write(compute_instruction(set_PC, halt, beq, gscore_pre, gscore, gscore_pre, gscore, 0, 0, gscore)) # gscore = gscore_pre > gscore ? gscore_pre : gscore
    # best global score
    f.write(compute_instruction(set_PC, halt, beq, cmp, 0, qle_pre, qle, 0, 0, qle))                     # qle = cmp > 0 ? qle_pre : qle
    # tracks the query end index
    f.write(compute_instruction(set_PC, halt, beq, cmp, 0, tle_pre, tle, 0, 0, tle))                     # tle = cmp > 0 ? tle_pre : tle
    # tracks target end index
    f.write(compute_instruction(set_PC, halt, beq, cmp, 0, max_off_pre, max_off, 0, 0, max_off))         # max_off = cmp > 0 ? max_off_pre : max_off
    # max offset for best alignment
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                                  # halt
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                                  # halt

    f.write(compute_instruction(add, halt, beq, max_ie, one, 0, 0, 0, 0, max_ie))                        # max_ie += 1
    f.write(compute_instruction(add, halt, beq, qle, one, 0, 0, 0, 0, qle))                              # qle += 1
    f.write(compute_instruction(add, halt, beq, tle, one, 0, 0, 0, 0, tle))                              # tle += 1
    # indexing changes for output
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                                  # halt
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                                  # halt
    f.write(compute_instruction(halt, halt, halt, 0, 0, 0, 0, 0, 0, 0))                                  # halt


def bsw_data():

    f.write(data_movement_instruction(gr, 0, 0, 0, 1, 0, 0, 0, 4, 0, si))                                   # gr[1] = pe_group_size
    # set amount of PEs in the group in the general register 1
    f.write(data_movement_instruction(gr, 0, 0, 0, 2, 0, 0, 0, 0, 0, si))                                   # gr[2] = 0
    # used as a counter 
    f.write(data_movement_instruction(gr, in_buf, 0, 0, 3, 0, 0, 1, 0, 2, mv))                              # gr[3] = input[gr[2]++]
    # read the first input parameter and increments gr2
    f.write(data_movement_instruction(gr, in_buf, 0, 0, 4, 0, 0, 1, 0, 2, mv))                              # gr[4] = input[gr[2]++]
    # loads next value from input buffer
    f.write(data_movement_instruction(gr, in_buf, 0, 0, 5, 0, 0, 1, 0, 2, mv))                              # gr[5] = input[gr[2]++]
    # loads next value from input buffer
    f.write(data_movement_instruction(reg, reg, 0, 0, PE_INIT_CONSTANT_AND_INSTRUCTION, 0, 0, 0, 0, 0, set_PC)) # PE_PC = consts&instr
    # sets PE program counter to initialization addresses
    for i in range(8):
        f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 0, 1, 0, 2, mv))                     # out = input[gr[2]++]
    # repeats 8 times, outputs values from the input buffer at gr2++ so if gr2 is 5, it outputs data at pos 5,6,7,8 etc.
    for i in range(BSW_COMPUTE_INSTRUCTION_NUM):
        f.write(data_movement_instruction(out_port, comp_ib, 0, 0, 0, 0, 0, 0, i, 0, mv))                    # out = instr[i]
    # sends compute instruction from the buffer to output port. maybe transfers instructions to the PE?

    f.write(data_movement_instruction(0, 0, 0, 0, 8, 0, 1, 0, 2, 3, add))                                   # gr[8] = gr[2] + gr[3]  
    # QUESTION HERE: WE CAN ADD CONTROL INFO TOGETHER?             
    f.write(data_movement_instruction(0, 0, 0, 0, 9, 0, 1, 0, 8, 3, add))                                   # gr[9] = gr[8] + gr[3]              
    f.write(data_movement_instruction(0, 0, 0, 0, 10, 0, 1, 0, 9, 4, add))                                  # gr[10] = gr[9] + gr[4]              
    # f.write(data_movement_instruction(0, 0, 0, 0, 10, 0, 0, 0, 3, 10, addi))                                # gr[10] = gr[10] + 3
    f.write(data_movement_instruction(gr, 0, 0, 0, 11, 0, 0, 0, 0, 0, si))                                  # gr[11] = 0       
    f.write(data_movement_instruction(fifo[0], in_buf, 0, 0, 0, 0, 0, 1, 0, 10, mv))                        # FIFO_H = input[gr[10]++]
    f.write(data_movement_instruction(fifo[1], gr, 0, 0, 0, 0, 0, 0, 0, 0, mv))                             # FIFO_E = gr[0]
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 0, 0, 1, 11, addi))                                # gr[11]++
    f.write(data_movement_instruction(0, 0, 0, 0, -3, 0, 1, 0, 11, 4, bne))                                 # bne gr[11] gr[4] -3
    # used as a loop, iterates until the counter in gr11 = gr4. want to keep processing the FIFO data


    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 1, 0, 0, 1, add))                                  # gr[11] = gr[1]              
    f.write(data_movement_instruction(0, 0, 0, 0, 3, 0, 1, 0, 3, 1, add))                                   # gr[3] = gr[3] + gr[1]
    f.write(data_movement_instruction(0, 0, 0, 0, 6, 0, 0, 0, 3, 4, addi))                                  # gr[6] = gr[4] + 3
    f.write(data_movement_instruction(gr, 0, 0, 0, 15, 0, 0, 0, 0, 0, si))                                  # gr[15] = 0       
    f.write(data_movement_instruction(0, 0, 0, 0, 96, 0, 1, 0, 11, 3, bge))                                 # bge gr[11] gr[3] 96
    # branch to instruction 96 if gr11 >= gr3. how does it go to 96? isnt that a reg/imm
    f.write(data_movement_instruction(gr, 0, 0, 0, 12, 0, 0, 0, -3, 0, si))                                 # gr[12] = 0 - 3
    f.write(data_movement_instruction(0, 0, 0, 0, 37, 0, 1, 0, 6, 11, bge))                                 # bge gr[6] gr[11] 37
    # same here, how?
    f.write(data_movement_instruction(0, 0, 0, 0, 12, 0, 1, 0, 11, 6, sub))                                 # gr[12] = gr[11] - gr[6]
    f.write(data_movement_instruction(0, 0, 0, 0, 5, 0, 1, 0, 12, 4, bge))                                  # bge gr[12] gr[4] 5
    f.write(data_movement_instruction(0, 0, 0, 0, 15, 0, 0, 0, 1, 15, addi))                                # gr[15]++
    f.write(data_movement_instruction(out_port, fifo[0], 0, 0, 0, 0, 0, 0, 0, 0, mv))                       # out = FIFO_H
    f.write(data_movement_instruction(out_port, fifo[1], 0, 0, 0, 0, 0, 0, 0, 0, mv))                       # out = FIFO_E
    f.write(data_movement_instruction(0, 0, 0, 0, -3, 0, 1, 0, 12, 15, bne))                                # bne gr[12] gr[15] -3
    f.write(data_movement_instruction(0, 0, 0, 0, 12, 0, 0, 0, -3, 12, addi))                               # gr[12] = gr[12] - 3

    
    f.write(data_movement_instruction(0, 0, 0, 0, PE_GROUP, 0, 0, 0, 0, 0, set_PC))                         # PE_PC = pe_group
    f.write(data_movement_instruction(0, 0, 0, 0, 14, 0, 0, 0, 0, 12, set_8))                               # gr[14] = set_8(gr[12])
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 14, 0, mv))                           # out = gr[14]
    for i in range(3):
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 0, 0, -1, 11, addi))                           # gr[11]--
    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 1, 0, 2, 11, mv))                   # out = input[gr[2](gr[11])]
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 0, 0, 0, 11, set_8))                            # gr[7] = set_8(gr[11])
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 7, 0, mv))                        # out = gr[7]
    f.write(data_movement_instruction(0, 0, 0, 0, 12, 0, 0, 0, 1, 12, addi))                            # gr[12]++
    f.write(data_movement_instruction(0, 0, 0, 0, 14, 0, 0, 0, 0, 12, set_8))                           # gr[14] = set_8(gr[12])
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 14, 0, mv))                       # out = gr[14]
    f.write(data_movement_instruction(0, 0, 0, 0, 11, 0, 0, 0, -1, 11, addi))                               # gr[11]--
    f.write(data_movement_instruction(out_port, in_buf, 0, 0, 0, 0, 1, 0, 2, 11, mv))                       # out = input[gr[2](gr[11])]
    f.write(data_movement_instruction(0, 0, 0, 0, 7, 0, 0, 0, 0, 11, set_8))                                # gr[7] = set_8(gr[11])
    f.write(data_movement_instruction(out_port, gr, 0, 0, 0, 0, 0, 0, 7, 0, mv))                            # out = gr[7]
    f.write(data_movement_instruction(0, 0, 0, 0, 33, 0, 0, 0, 0, 0, beq))                                  # beq 0 0 33