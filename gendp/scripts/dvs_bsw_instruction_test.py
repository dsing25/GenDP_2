def compute_instruction(op_0, op_1, op_2, in_addr_0, in_addr_1, in_addr_2, in_addr_3, in_addr_4, in_addr_5, out_addr):

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

