FILE_LIST = ./.installed_files.txt

.PHONY: pull push clean install post-install uninstall

default: | pull clean install post-install

install:
	@ ./setup.py install --record $(FILE_LIST)

post-install:
	@ fixuwsgi hisecon

uninstall:
	@ while read FILE; do echo "Removing: $$FILE"; rm "$$FILE"; done < $(FILE_LIST)

clean:
	@ rm -Rf ./build

pull:
	@ git pull

push:
	@ git push
