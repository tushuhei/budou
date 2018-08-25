install-mecab:
	git clone https://github.com/taku910/mecab.git; \
	cd mecab/mecab; \
	./configure  --enable-utf8-only; \
	make; \
	make check; \
	make install; \
	ldconfig; \
	cd ../mecab-ipadic; \
	./configure --with-charset=utf8; \
	make; \
	make install; \
	mecab --version; \

doc:
	make install; \
	sphinx-apidoc -F -o docs/ budou/; \
	sphinx-build -b html docs/ docs/_build/
