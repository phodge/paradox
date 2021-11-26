FROM ubuntu:20.04

RUN apt update

RUN apt-get -y install software-properties-common

RUN apt-add-repository ppa:deadsnakes/ppa && apt-get update

RUN apt-get install -y python3.10

# adding these back in because we didn't have disutils.util needed by the get-pip.py script
RUN apt-get install -y python3.10-full

# needed for the poetry install, but has to come before get-pip.py installer
RUN apt-get install -y python3-distutils
RUN apt-get install -y gcc
# comes with gcc:
####  binutils binutils-common binutils-x86-64-linux-gnu cpp cpp-9 gcc gcc-9 gcc-9-base libasan5 libatomic1 libbinutils libc-dev-bin libc6-dev libcc1-0 libcrypt-dev libctf-nobfd0 libctf0 libgcc-9-dev libgomp1 libisl22 libitm1 liblsan0 libmpc3 libmpfr6 libquadmath0 libtsan0 libubsan1 linux-libc-dev manpages manpages-dev
####  binutils binutils-common binutils-x86-64-linux-gnu build-essential cpp cpp-9 dpkg-dev fakeroot g++ g++-9 gcc-9 gcc-9-base libalgorithm-diff-perl
####  libalgorithm-diff-xs-perl libalgorithm-merge-perl libasan5 libatomic1 libbinutils libc-dev-bin libc6-dev libcc1-0 libcrypt-dev libctf-nobfd0 libctf0
####  libdpkg-perl libexpat1-dev libfakeroot libfile-fcntllock-perl libgcc-9-dev libgdbm-compat4 libgdbm6 libgomp1 libisl22 libitm1 liblocale-gettext-perl
####  liblsan0 libmpc3 libmpfr6 libperl5.30 libpython3-dev libpython3.8 libpython3.8-dev libquadmath0 libstdc++-9-dev libtsan0 libubsan1 linux-libc-dev make
####  manpages manpages-dev netbase patch perl perl-modules-5.30 python-pip-whl python3-dev python3-distutils python3-lib2to3 python3-pip python3-setuptools
####  python3-wheel python3.8-dev zlib1g-dev

## this is needed for pip to be able to install poetry
RUN apt-get install wget
RUN wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py && python3.10 /tmp/get-pip.py && rm -f /tmp/get-pip.py
#RUN wget https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3.10 /tmp/get-pip.py && rm -f /tmp/get-pip.py
#
# XXX this is needed to get poetry to install (cffi)
RUN apt-get install -y python3.10-dev libffi-dev && python3.10 -m pip install poetry && apt-get remove -y python3.10-dev libffi-dev
#
WORKDIR /paradox

RUN cd /paradox

COPY . .

RUN poetry config virtualenvs.create false
RUN poetry install
RUN cd tests && pytest
