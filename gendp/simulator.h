#ifndef SIMGLOBALS_H
#define SIMGLOBALS_H
#include <set>
#include <list>
#include "sys_def.h"


extern int cycle;

inline int lineAddr(int addr) { return (addr >> 1) << 1; }
inline int lineOffset(int addr) { return addr & 1; }

typedef int PerfCounter;
extern PerfCounter totalSpmRequests;
extern PerfCounter bankConflictStalls;

enum EventType {
    SPM_DATA_READY
};

class Event {
    public:
        EventType type;
        void* data;
        Event(EventType t, void* d) : type(t), data(d) {}
};

class EventProducer {
    /*
     * processes one timestep for this unit. Then returns bool (true if unit still has work to do, 
     * i.e. tick should be called in next cycle) and linkedlist<Events> which contains events to be 
     * processed by PE_array generated from this unit.
     */
    public:
        virtual std::pair<bool, std::list<Event>*> tick() = 0;
};

/*
 * Limited version of producer list that you can add to, but can't read or delete from.
 * Usefull because only the pe_array should have those priveleged
 */
class PushableProducerSet {
    public:
        PushableProducerSet(std::set<EventProducer*>* p) : producers(p) {}
        inline void push(EventProducer* producer) { producers->insert(producer); }
    private:
        std::set<EventProducer*>* producers;
};

/*
 * This is used within a PE for loads to/from SPM
 */
struct LoadResult {
    int data[SPM_BANDWIDTH];
    LoadResult() {
        for (int i = 0; i < SPM_BANDWIDTH; i++) {
            data[i] = 42;
        }
    }
};

/*
 * Modular integer for circular buffer indexing.
 * Automatically wraps on arithmetic operations.
 */
class ModInt {
    public:
        int val;
        int size;

        ModInt(int size, int initial_value = 0);

        ModInt& operator+=(int offset);
        ModInt& operator-=(int offset);
        ModInt operator+(int offset) const;
        ModInt operator-(int offset) const;
        ModInt& operator++();
        ModInt operator++(int);
        ModInt& operator--();
        ModInt operator--(int);

        operator int() const { return val; }

    private:
        int normalize(int v) const;
};

#endif // SIMGLOBALS_H

//class or callback. I want it to have the context of SPM, and some of it's own context (like where
//        to put the data later. How about SPM interits from interface containing callback.
//        Queue contains struct SPMCallbackData inherits from CallbackData, and it contains pointer
//        to object that implements callback interface. now each cycle we pass CallbackData to 
//        callback. My only concern is that this could be a bit over complex, but what if one class
//        has multiple callbacks? Then this sounds bad. Really what I want is an object holding some
//        stat like dest. This is not really part of SPM, so ideally we don't want to putu it there. 
//        In fact, the callback that we need to do here is not part of SPM because we need to write
//        regfile. We essentially need to call "run" of SPM and then o
//        How about SPM is a class which implements the tick method. If it is in the queue, that
//        means at least one thing is ticking. All updates in SPM are done in tick. Tick then returns
//        a list of events for PE to handle. Nah, cause we'll have many PEs. Each should be able to 
//        call tick.
//        Basically we're talking about ports. I think ports are overkill, and there's no 
//        infrastructure for it. If we don't go with ports, let's manually have the pe_array route
//        the data results between unit and pe. it'll be the point of synchronization
//        right so communication is taken care of. 
//
//        OK 


