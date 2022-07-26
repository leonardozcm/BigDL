#!/usr/bin/env bash

#
# Copyright 2016 The BigDL Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# This is the default script with maven parameters to release all the bigdl sub-packages
# built on top of Spark for linux.

set -e
RUN_SCRIPT_DIR=$(cd $(dirname $0) ; pwd)
echo $RUN_SCRIPT_DIR
BIGDL_DIR="$(cd ${RUN_SCRIPT_DIR}/../..; pwd)"
echo $BIGDL_DIR

if (( $# < 4)); then
  echo "Usage: release_default_linux_spark.sh version quick_build upload spark_version suffix mvn_parameters"
  echo "Usage example: bash release_default_linux_spark.sh default false true 3.1.2 true"
  echo "Usage example: bash release_default_linux_spark.sh 0.14.0.dev1 false false 2.4.6 true"
  echo "Usage example: bash release_default_linux_spark.sh 0.14.0.dev1 false false 2.4.6 false -Ddata-store-url=.."
  exit -1
fi

version=$1
quick=$2
upload=$3
spark_version=$4

array=(${spark_version//./ })
spark_first_version=${array[0]}

re='^[2-3]+$'
if ! [[ $spark_first_version =~ $re ]] ; then
   echo "error: Spark version is not a number like 3.1.2"
   exit 1
fi

if (( $# < 5)); then
  suffix=false
  profiles=${*:5}
else
  suffix=$5
  profiles=${*:6}
fi

# Nano and serving are released in release_default_linux.sh as they don't rely on spark versions.

# Only dllib is not using quick build.
# Since make_dist is invoked in dllib, all other packages can directly use quick build.
DLLIB_SCRIPT_DIR="$(cd ${BIGDL_DIR}/python/dllib/dev/release; pwd)"
echo $DLLIB_SCRIPT_DIR
bash ${DLLIB_SCRIPT_DIR}/release_default_linux_spark.sh ${version} ${quick} ${upload} ${spark_version} ${suffix} ${profiles}

ORCA_SCRIPT_DIR="$(cd ${BIGDL_DIR}/python/orca/dev/release; pwd)"
echo $ORCA_SCRIPT_DIR
bash ${ORCA_SCRIPT_DIR}/release_default_linux_spark.sh ${version} true ${upload} ${suffix}

FRIESIAN_SCRIPT_DIR="$(cd ${BIGDL_DIR}/python/friesian/dev/release; pwd)"
echo $FRIESIAN_SCRIPT_DIR
bash ${FRIESIAN_SCRIPT_DIR}/release_default_linux_spark.sh ${version} true ${upload} ${suffix}

CHRONOS_SCRIPT_DIR="$(cd ${BIGDL_DIR}/python/chronos/dev/release; pwd)"
echo $CHRONOS_SCRIPT_DIR
bash ${CHRONOS_SCRIPT_DIR}/release_default_linux_spark.sh ${version} ${upload} ${suffix}

bash ${RUN_SCRIPT_DIR}/release_bigdl_spark${spark_first_version}.sh linux ${version} ${upload} ${suffix}
