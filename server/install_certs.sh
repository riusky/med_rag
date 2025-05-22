#!/bin/bash

# PEM content for the certificates
GEHEALTHCAREROOTCA1_PEM=$(cat <<EOL
subject=C = US, O = GE HealthCare, OU = Enterprise, CN = GE HealthCare Root CA 1
issuer=C = US, O = GE HealthCare, OU = Enterprise, CN = GE HealthCare Root CA 1
-----BEGIN CERTIFICATE-----
MIIFtTCCA52gAwIBAgIQbV1lbakySiHTPT1W7bY6bjANBgkqhkiG9w0BAQsFADBc
MQswCQYDVQQGEwJVUzEWMBQGA1UEChMNR0UgSGVhbHRoQ2FyZTETMBEGA1UECxMK
RW50ZXJwcmlzZTEgMB4GA1UEAxMXR0UgSGVhbHRoQ2FyZSBSb290IENBIDEwHhcN
MjMwMTI1MDAwMDAwWhcNNDMwMTI0MjM1OTU5WjBcMQswCQYDVQQGEwJVUzEWMBQG
A1UEChMNR0UgSGVhbHRoQ2FyZTETMBEGA1UECxMKRW50ZXJwcmlzZTEgMB4GA1UE
AxMXR0UgSGVhbHRoQ2FyZSBSb290IENBIDEwggIiMA0GCSqGSIb3DQEBAQUAA4IC
DwAwggIKAoICAQC6NKB3bEgLIfDbrPd5djGvqm+wcAqvMWmuH3u2cPBE+Z+3NYq6
VjB9fAgDpBk/wNen52D/20bYvutPOPhmKkLHKqc51x4K6Ympi0jTZqkFfnePvDA8
FTI6UoeECJZGHk1j0e1JoPJTaGDiw9aMDDTdq+qP02eAC8LdUyEd2lVzKqpGHiOq
1BSy7I9rle8rTeoOG6Sqemb3hdkMK1+VRP7dVDuGHCe+CR4FJI345LMLnEb01LEZ
uI0+7E+9I8wN96iOo9VpfmvnUp1Tp+t5YbRJ3e+5ml8Wjzk45lhg8EuBf0xVnBZj
w5iUaaSaHMKemJzgixhtsHO9yp1RfGt69CeFaeBYoqHwKQ//IH0ffS8bRifA73Uc
7AM3/LrL7l4mr/8metDb8F2ixE/1okNrRD9nhnzl6VPXjHxcsE/JcEUiDJ+4SiHW
poLFRSQwyqvMszfXyTiIbj1o3ss5Jdgbqr46jkcManVX2PCEMo8T1LR4jZ+Y7xSw
zLM2ZA2tSiqS6J26bzU1ZB3L8juTFbiNC3OIggcAedoAKAPH695iBLNakJFWft+O
fuYeTYRCQC3VpWju7z9uVS7VJl6aJHu8xjD9yBuL/ze2TBpGLU2tFShwaJNWI4RC
viUnDw5mITu/mDSQAH72TDDZu/HkdHp/OY+Waptw04LnzIAffdlvMgKo7QIDAQAB
o3MwcTAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAvBgNVHREEKDAm
pCQwIjEgMB4GA1UEAxMXZ2VoYy1vZmZsaW5lLXJzYS00MDk2LTYwHQYDVR0OBBYE
FDx2YI415NU2FJq1thMsK8idMTF/MA0GCSqGSIb3DQEBCwUAA4ICAQAoyTJqhBAT
2fI0QJk/dSylUgSSW2jmqtb5sDlwT9GTa+USM1H/EqUQbfeXKMEXlsAw3EXIofLI
i5bAmmpY0U75C8QFy8A9u0dE9EgjqBqCxckxQuV9LrtGRu+V5exeg6lBu5naZhsH
IF0hirkO2XHazy2pbMdyk5rrcc7Jm6PEo98Onlcf6qEJZ1E74n85pKRS8XahSxL9
Z7BmThfyng8uBBdP/V8AHSDt/Y1iinXO8XYPdwe3XjeG4oJemjsTxGjzSdlkonHN
44x4FLj/DmDnjfelXgfn4pPG6LM1y3FmPYAIK6coLUZ3foQHrluyEYMhRBvG87Oj
fVUXRp6ziw32b2R76JRDalKJxZfILPw/UVgx0cc/7bsmO1GphqcaDOT999fFZX+n
SwjSOsBuQVXZ7hQe8O8AXwpSbgE827nRcmVeB5sNJq7Bzv2Eze1OKeflLC6LF4nM
/vCa2axgnvJuIaJVciDeQiIJcmRXFgKwpwU6h9330bV+FEP7mjdZ08/b8EAlBMbG
E/dtyjuQApz3DCaWQJQ0cGzRv07RDfuhyPN5GnBcPDvjMNcUXIdaz14trUIH3w51
gsjGC5MfOOYKIeCs0H/tPZXelmWqQnEYvcJdSSCw+K7aTO+bJUsmMCHRMHZlnv/O
FFjbQbsta/8zJTRm7OxMdYWCE2K5/HOMVg==
-----END CERTIFICATE-----
EOL
)

GEHEALTHCAREROOTCA2_PEM=$(cat <<EOL
subject=C = US, O = GE HealthCare, OU = Enterprise, CN = GE HealthCare Root CA 2
issuer=C = US, O = GE HealthCare, OU = Enterprise, CN = GE HealthCare Root CA 2
-----BEGIN CERTIFICATE-----
MIICsDCCAhKgAwIBAgIQSqlMwD5PlPQtI+siCcRE1zAKBggqhkjOPQQDBDBcMQsw
CQYDVQQGEwJVUzEWMBQGA1UEChMNR0UgSGVhbHRoQ2FyZTETMBEGA1UECxMKRW50
ZXJwcmlzZTEgMB4GA1UEAxMXR0UgSGVhbHRoQ2FyZSBSb290IENBIDIwHhcNMjMw
MTI1MDAwMDAwWhcNNDMwMTI0MjM1OTU5WjBcMQswCQYDVQQGEwJVUzEWMBQGA1UE
ChMNR0UgSGVhbHRoQ2FyZTETMBEGA1UECxMKRW50ZXJwcmlzZTEgMB4GA1UEAxMX
R0UgSGVhbHRoQ2FyZSBSb290IENBIDIwgZswEAYHKoZIzj0CAQYFK4EEACMDgYYA
BADszeX2cNbSHbfaVQlzfnTg8gZMT88oE42t4u8KgwYpYiZIpbGUzzORM99+9Ja8
NuNn0IXIbrdYBr6EmUfFoN9vQQBmkFFlq58WIOTOVdkgpyiSRCIcgldyqsLTTaNz
2tyA8oN7DVgY6RAMGA63uIC9/HEJQthU5n74t58DmPKJQIqUg6NzMHEwDwYDVR0T
AQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAYYwLwYDVR0RBCgwJqQkMCIxIDAeBgNV
BAMTF2dlaGMtb2ZmbGluZS1lY2MtNTIxLTIxMB0GA1UdDgQWBBRWrgYPVMNSazyM
86QbMJbVqUP9PjAKBggqhkjOPQQDBAOBiwAwgYcCQgCd+mYJhRxZihokECePXG7E
A4lrfGBZvptxtK819BnEgIpTCOOgwoy3MLfvrxZO65gp2KFIDOw+WFEkYbhVqJEo
ZgJBOxGDQcsuU7ZHz42z174ODulVnSUrgQNVVsW7dc03JIdiDfWsm3ttGOeGT7Qy
MLsr780Rm1bBBBpclqRBNcaZMR8=
-----END CERTIFICATE-----
EOL
)


# Define the PEM file paths
GEHEALTHCAREROOTCA1_FILE="/tmp/gehealthcarerootca1.pem"
GEHEALTHCAREROOTCA2_FILE="/tmp/gehealthcarerootca2.pem"

# Save the PEM content to files
echo "$GEHEALTHCAREROOTCA1_PEM" > "$GEHEALTHCAREROOTCA1_FILE"
echo "$GEHEALTHCAREROOTCA2_PEM" > "$GEHEALTHCAREROOTCA2_FILE"


# Determine the Linux distribution
if [ -f /etc/os-release ]; then
    source /etc/os-release
    LINUX_DISTRO=$ID
    #echo "Check Linux Distro"
    #echo $LINUX_DISTRO
else
    echo "Unable to determine Linux distribution. Exiting."
    exit 1
fi

# Function to install certificates based on the distribution
install_certificates() {
    if [ `which apt 2> /dev/null` ]; then
        #sudo apt-get update
        sudo apt-get install -y ca-certificates
        sudo mv "$GEHEALTHCAREROOTCA1_FILE" "/usr/local/share/ca-certificates/gehealthcarerootca1.crt"
        sudo mv "$GEHEALTHCAREROOTCA2_FILE" "/usr/local/share/ca-certificates/gehealthcarerootca2.crt"
        sudo update-ca-certificates
    elif [ "$LINUX_DISTRO" == "rhel" ] || [ "$LINUX_DISTRO" == "centos" ] || [ "$LINUX_DISTRO" == "ol" ] || [ "$LINUX_DISTRO" == "amzn" ]; then
        sudo mv "$GEHEALTHCAREROOTCA1_FILE" "/etc/pki/ca-trust/source/anchors/gehealthcarerootca1.crt"
        sudo mv "$GEHEALTHCAREROOTCA2_FILE" "/etc/pki/ca-trust/source/anchors/gehealthcarerootca2.crt"
        sudo update-ca-trust
    elif [ "$LINUX_DISTRO" == "sles" ]; then
        sudo cp "$GEHEALTHCAREROOTCA1_FILE" /etc/pki/trust/anchors/ 
        sudo cp "$GEHEALTHCAREROOTCA2_FILE" /etc/pki/trust/anchors/
        sudo cp "$GEHEALTHCAREROOTCA1_FILE" /usr/share/pki/trust/anchors/ 
        sudo cp "$GEHEALTHCAREROOTCA2_FILE" /usr/share/pki/trust/anchors/
        sudo update-ca-certificates
    else
        echo "Unsupported or unrecognized Linux distribution. Exiting."
        exit 1
    fi

}

# Call the function to install certificates
install_certificates
