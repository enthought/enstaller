default: foo_x86 foo_amd64

foo_rpath.dylib: src/foo.c
	$(CC) $< -o $@ -shared -install_name $@
	install_name_tool -add_rpath @loader_path/../lib $@

foo_legacy_placehold_lc_dylib.dylib: src/foo.c libfoo.dylib
	$(CC) $< -o $@ -shared -install_name $@ -L . -lfoo

foo_legacy_placehold_lc_rpath.dylib: src/foo.c
	$(CC) $< -o $@ -shared -install_name $@
	install_name_tool -add_rpath /PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD $@

foo_x86: src/empty_main.c
	$(CC) $< -o $@ -arch i386

foo_amd64: src/empty_main.c
	$(CC) $< -o $@ -arch x86_64

libfoo.dylib: src/foo.c
	$(CC) $< -o $@ -shared -install_name /PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/PLACEHOLD/libfoo.dylib

foo.so: src/empty.c
	$(CC) $< -o $@ -bundle -L. -lfoo

clean:
	rm -f foo_x86
	rm -f foo_amd64
