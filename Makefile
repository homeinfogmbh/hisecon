FILE_LIST = ./.installed_files.txt

.PHONY: pull push clean backend frontend install uninstall

default: pull clean install

backend:
	@ install -m 644 hisecon.mjs /srv/http/de/homeinfo/javascript/hisecon.mjs

frontend:
	@ install -m 644 hisecon.mjs /srv/http/de/homeinfo/javascript/hisecon.mjs

install: backend frontend

uninstall:
	@ while read FILE; do echo "Removing: $$FILE"; rm "$$FILE"; done < $(FILE_LIST)

clean:
	@ rm -Rf ./build

pull:
	@ git pull

push:
	@ git push
