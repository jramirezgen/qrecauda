#!/usr/bin/env bash
# Compila el NIST SP800-90B_EntropyAssessment v1.1.8 (C++ oficial) FUERA del repo, sin root.
# Uso: bash build_nist.sh [DIR]   (por defecto /tmp/qrecauda_nist90b). Imprime la ruta de ea_non_iid.
set -euo pipefail
TAG=v1.1.8
D=${1:-/tmp/qrecauda_nist90b}
mkdir -p "$D/deps" && cd "$D"
if [ ! -x "$D/ea_non_iid" ]; then
  [ -f src.tgz ] || curl -sfL -o src.tgz "https://github.com/usnistgov/SP800-90B_EntropyAssessment/archive/refs/tags/$TAG.tar.gz"
  tar xzf src.tgz
  # Dependencias de desarrollo sin sudo: apt-get download + dpkg -x a un prefijo local
  (cd deps && apt-get download libbz2-dev libdivsufsort-dev libdivsufsort3 libjsoncpp-dev libjsoncpp25 >/dev/null 2>&1 \
     && for f in *.deb; do dpkg -x "$f" root; done)
  R="$D/deps/root"; M=/usr/lib/x86_64-linux-gnu
  cd "SP800-90B_EntropyAssessment-${TAG#v}/cpp"
  g++ -std=c++11 -fopenmp -O2 -ffloat-store -msse2 -march=native \
    -I"$R/usr/include" -I"$R/usr/include/x86_64-linux-gnu" -I"$R/usr/include/jsoncpp" non_iid_main.cpp -o "$D/ea_non_iid" \
    -L"$R/usr/lib/x86_64-linux-gnu" -L"$M" -Wl,-rpath,"$R/usr/lib/x86_64-linux-gnu" \
    -l:libbz2.so.1.0 -lpthread -ldivsufsort -ldivsufsort64 -ljsoncpp -lcrypto
fi
echo "$D/ea_non_iid"
