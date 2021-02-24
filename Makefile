FILE_LIST = ./.installed_files.txt

.PHONY: pull push clean install uninstall

default: | pull clean install

install:
	@ ./setup.py install --record $(FILE_LIST)
	@ install -m 644 hisecon.mjs /srv/http/de/homeinfo/javascript/hisecon.mjs

uninstall:
	@ while read FILE; do echo "Removing: $$FILE"; rm "$$FILE"; done < $(FILE_LIST)

clean:
	@ rm -Rf ./build
