# High level
There are some simulator features assumed in the GWFA magic instructions that are not yet built in.
We will add them here

# Features
1. MM is right now a 4GB block of memory, but we don't have a way to access it. I want to add a
   destination/src just like s2 that allows you to access MM. It should be possible to do gr<->MM
   and MM<->SPM. 
   MM will have a fixed latency of 100 cycles configurable as MM_LATENCY. We won't bother to keep
   track of stores. As soon as a store is issued with destination MM, it will magically write
   everything to MM, but we will keep a counter, lastMMStore, which is reset to MM_LATENCY whenever 
   a store
   is issued to MM. Every cycle it is decremented. waitLsq should not pass until lastMMStore is < 0.
   This is basically just to make sure that all stores are flushed before waitLsq finishes.

   For loads, we will maintain a queue of MEM_LATENCY entries. Each entry can hold up to 8 data
   slots (for an mvdq). They hold the destination address and the destination id (e.g. spm or gr). 
   They also maintain a timer which starts from 100 and decrements each cycle. When it reaches 0 the
   load is deleted from the queue. If dest was SPM, it is inserted into the SPM queue. If instead it
   was gr, then we immediately write to the appropriate gr register.

   MM should probably become a class which holds the current 4GB structure
2. For s1c, enable mvd from s1c<->spm. This means you'll need yet another queue to handle memory
   moves coming from spm into s1c. Controller reads from s1c to gr should bypass that queue, but
   waitLsq should wait for that queue to drain.
