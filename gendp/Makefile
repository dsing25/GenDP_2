LINK    = @echo linking $@ && g++
CXX     = @echo compiling $@ && g++
AR      = @echo generating static library $@ && ar rc

# LINK    = g++
# CXX     = g++
# AR      = ar rc

#BASE CXXFLAGS
#CXXFLAGS   = -g -Wall -Wno-format -Wno-unused-variable -Wno-unused-but-set-parameter -Wno-unused-result -fPIC -std=c++11 -O0 -g3 -fno-inline -fno-omit-frame-pointer -fno-lto -fvar-tracking -fvar-tracking-assignments -lpthread 
CXXFLAGS   = -g -g3 -ggdb -O0 -std=c++11
#CXXFLAGS   += -Wall -Wextra -Wpedantic
HEADER  = 
LIBS    = libsimulator.a 
LINKFLAGS = 

# Default: ADDRESS_SANITIZER is not enabled
ADDRESS_SANITIZER ?= 1
ifeq ($(ADDRESS_SANITIZER),1)
    CXXFLAGS += -fsanitize=address -fno-omit-frame-pointer -static-libasan
    LINKFLAGS += -fsanitize=address
endif


OBJECT 	:= 	main.o bsw.o poa.o chain.o phmm.o wfa.o bankThrasher.o simulator.o

ifeq ($(debug),1)
CXXFLAGS+= -DDEBUG
endif

ifeq ($(profile),1)
CXXFLAGS+= -DPROFILE
endif

LIB_SIMULATOR_OBJECTS= \
			alu_32.o \
			compute_unit_32.o \
			crossbar.o \
			regfile.o \
			comp_decoder.o \
			data_buffer.o \
			pe.o \
			FIFO.o \
			pe_array.o

BIN_PATH = ./

TARGET = sim

$(TARGET) : $(OBJECT) $(LIBS)
	$(LINK) $(FLAGS) $(LINKFLAGS) -o $@ $^

.cpp.o:
	$(CXX) -c $(HEADER) $(CXXFLAGS) -fpermissive -o $@ $<

libsimulator.a:  $(LIB_SIMULATOR_OBJECTS)
	rm -f $@
	$(AR) $@ $(LIB_SIMULATOR_OBJECTS)
	ranlib $@

# libkernel.a: bsw.o poa.o chain.o
# 	rm -f $@
# 	$(AR) $@ bsw.o poa.o chain.o
# 	ranlib $@

install: $(TARGET)
	cp $(TARGET) $(BIN_PATH)

clean:
	rm -rf $(TARGET) *.o *.so *.a
