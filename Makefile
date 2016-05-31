
FILE_LIST = ./.installed_files.txt

install:
	@ ./setup.py install --record ${FILE_LIST}

uninstall:
	@ while read FILE; do
		rm "${FILE}"
	done < ${FILE_LIST}

clean:
	@ rm -R ./build

check:
	@ find . -type f -name "*.py" -not -path "./build/*" -exec pep8 --hang-closing {} \;

pull:
	@ git pull

push:
	@ git push

compile:
	@ ./compile.sh /usr/bin/retard
	@ ./compile.sh /usr/bin/homiectl
