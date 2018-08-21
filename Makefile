init:
	pip install -r requirements.txt

init-dev:
	make init
	pip install -r requirements_dev.txt
	make install-mecab

install:
	python setup.py install

install-mecab:
	git clone https://github.com/taku910/mecab.git; \
	cd mecab/mecab; \
	./configure  --enable-utf8-only; \
	make; \
	make check; \
	sudo make install; \
	cd ../mecab-ipadic; \
	./configure --with-charset=utf8; \
	make; \
	sudo make install; \

test:
	nosetests tests

docs:
	sphinx-apidoc -F -o docs/ budou/; \
	sphinx-build -b html docs/ docs/_build/
