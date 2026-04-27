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

# Core kernels (always built).
OBJECT 	:= 	main.o bsw.o poa.o chain.o phmm.o wfa.o bankThrasher.o simulator.o

# GWFA kernel is optional: only included when kernel/Gwfa/gwfa.c is present
# (submodule initialized). Users who have not fetched that submodule can
# still build sim for the legacy kernels without the Gwfa sources.
ifneq ($(wildcard kernel/Gwfa/gwfa.c),)
OBJECT 	+= 	gwfa_sim.o
WITH_GWFA := 1
endif

ifeq ($(debug),1)
CXXFLAGS+= -DDEBUG
endif

ifeq ($(profile),1)
CXXFLAGS+= -DPROFILE
endif

ifeq ($(plan3c_snap),1)
CXXFLAGS+= -DPLAN3C_TRACE_SNAPSHOT
endif

ifeq ($(plan3d_snap),1)
CXXFLAGS+= -DPLAN3D_TRACE_SNAPSHOT
endif

# GWFA seam / clamp tracing. Off by default (otherwise thousands of
# stderr lines dominate routine -k 7 runs). Enable with
# `make gwfa_seam_trace=1` for debugging the m29/m31 seam handshake.
ifeq ($(gwfa_seam_trace),1)
CXXFLAGS+= -DGWFA_SEAM_TRACE
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

# gwfa_kernel.o mirrors the OBJECT-level gate: only build it when the
# Gwfa submodule is present.
ifeq ($(WITH_GWFA),1)
LIB_SIMULATOR_OBJECTS += gwfa_kernel.o
endif

BIN_PATH = ./

TARGET = sim

# O3 optimized build
CXXFLAGS_O3 = -O3 -std=c++11

# Both the debug build (CXXFLAGS) and the release build (CXXFLAGS_O3)
# need matching preprocessor feature flags so both TUs see the same
# #ifdef-guarded code.
ifeq ($(WITH_GWFA),1)
CXXFLAGS    += -DGWFA_BUILD
CXXFLAGS_O3 += -DGWFA_BUILD
endif

# Stamp file that tracks the current WITH_GWFA + snapshot/trace flag
# state. `make` cannot see CXXFLAGS changes, so a previously-built
# tree (with one set of preprocessor defines) would silently reuse
# stale main.o / pe.o / pe_array.o on the next `make ... <flag>=1
# sim` invocation, masking #ifdef-guarded code from the new build.
# The stamp rule rewrites .gwfa_state only when ANY tracked variable
# flips (WITH_GWFA, plan3c_snap, plan3d_snap, gwfa_seam_trace); the
# rewrite bumps mtime, so the gated TUs below rebuild automatically.
# Plan 3d Round 10 l9c P2 fix per Codex review: prior version
# tracked only WITH_GWFA, so `make plan3d_snap=1 sim` after a
# normal build silently produced no snapshot files unless the user
# remembered to `make clean` first.
.PHONY: .gwfa_state_FORCE
.gwfa_state: .gwfa_state_FORCE
	@echo "WITH_GWFA=$(WITH_GWFA)|plan3c_snap=$(plan3c_snap)|plan3d_snap=$(plan3d_snap)|gwfa_seam_trace=$(gwfa_seam_trace)" > $@.tmp
	@if ! cmp -s $@.tmp $@ 2>/dev/null; then mv $@.tmp $@; \
	else rm -f $@.tmp; fi
.gwfa_state_FORCE:

main.o pe.o pe_array.o main_o3.o pe_o3.o pe_array_o3.o: .gwfa_state
ifeq ($(gwfa_seam_trace),1)
CXXFLAGS_O3 += -DGWFA_SEAM_TRACE
endif
ifeq ($(plan3c_snap),1)
CXXFLAGS_O3 += -DPLAN3C_TRACE_SNAPSHOT
endif
ifeq ($(plan3d_snap),1)
CXXFLAGS_O3 += -DPLAN3D_TRACE_SNAPSHOT
endif
TARGET_O3 = sim_o3
OBJECT_O3 = $(OBJECT:.o=_o3.o)
LIB_O3 = libsimulator_o3.a
LIB_OBJECTS_O3 = $(LIB_SIMULATOR_OBJECTS:.o=_o3.o)

.PHONY: all clean install

all: $(TARGET) $(TARGET_O3)

$(TARGET) : $(OBJECT) $(LIBS)
	$(LINK) $(FLAGS) $(LINKFLAGS) -o $@ $^

.cpp.o:
	$(CXX) -c $(HEADER) $(CXXFLAGS) -fpermissive -o $@ $<

gwfa_kernel.o: kernel/Gwfa/gwfa.c kernel/Gwfa/gwfa.h
	@echo compiling $@ && gcc -c -O3 -Ikernel/Gwfa -o $@ $<

gwfa_kernel_o3.o: kernel/Gwfa/gwfa.c kernel/Gwfa/gwfa.h
	@echo compiling $@ && gcc -c -O3 -Ikernel/Gwfa -o $@ $<

libsimulator.a:  $(LIB_SIMULATOR_OBJECTS)
	rm -f $@
	$(AR) $@ $(LIB_SIMULATOR_OBJECTS)
	ranlib $@

# O3 optimized build targets
%_o3.o: %.cpp
	@echo compiling $@ && g++ -c $(HEADER) $(CXXFLAGS_O3) -fpermissive -o $@ $<

$(TARGET_O3): $(OBJECT_O3) $(LIB_O3)
	@echo linking $@ && g++ -o $@ $^

$(LIB_O3): $(LIB_OBJECTS_O3)
	rm -f $@
	@echo generating static library $@ && ar rc $@ $(LIB_OBJECTS_O3)
	ranlib $@

# libkernel.a: bsw.o poa.o chain.o
# 	rm -f $@
# 	$(AR) $@ bsw.o poa.o chain.o
# 	ranlib $@

install: $(TARGET)
	cp $(TARGET) $(BIN_PATH)

clean:
	rm -rf $(TARGET) $(TARGET_O3) *.o *_o3.o *.so *.a
