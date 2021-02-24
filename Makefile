FILE_LIST = ./.installed_files.txt

.PHONY: backend frontend uninstall clean pull push

default: | pull clean install

install: | backend frontend

backend:
	@ ./setup.py install --record $(FILE_LIST)

frontend:
	@ install -m 644 hisecon.mjs /srv/http/de/homeinfo/javascript/hisecon.mjs

uninstall:
	@ while read FILE; do echo "Removing: $$FILE"; rm "$$FILE"; done < $(FILE_LIST)

clean:
	@ rm -Rf ./build

pull:
	@ git pull

push:
	@ git push
