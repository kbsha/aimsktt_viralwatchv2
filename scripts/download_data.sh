!/bin/bash

mkdir -p data/raw/who_pdfs


echo "Downloading WHO PDF data..."


curl -L \
"https://www.who.int/docs/default-source/coronaviruse/situation-reports/example.pdf" \
-o data/raw/who_pdfs/outbreak_report.pdf


echo "Download finished"


file data/raw/who_pdfs/outbreak_report.pdf
