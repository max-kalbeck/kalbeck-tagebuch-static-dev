#!/bin/bash
if [ $# -eq 0 ]; then
  BRANCH=dev
else
  BRANCH="$1"
fi
echo ${BRANCH}
rm -rf kalbeck-tagebuch-static* html xslt *.zip build.xml saxon *scripts *lock
curl -L -o "${BRANCH}.zip" "https://github.com/max-kalbeck/kalbeck-tagebuch-static/archive/${BRANCH}.zip"
unzip ${BRANCH}.zip
rm -f kalbeck-tagebuch-static-${BRANCH}/pyproject.toml kalbeck-tagebuch-static-${BRANCH}/README*   kalbeck-tagebuch-static-${BRANCH}/set* 
mv kalbeck-tagebuch-static-${BRANCH}/*.* ./
mv kalbeck-tagebuch-static-${BRANCH}/{saxon,xslt,html,*scripts} .
echo 'rm -rf data/editions' >> shellscripts/fetch_data.sh
echo 'mv data/work data/editions' >> shellscripts/fetch_data.sh

rm -rf kalbeck-tagebuch-static-app-${BRANCH}*
