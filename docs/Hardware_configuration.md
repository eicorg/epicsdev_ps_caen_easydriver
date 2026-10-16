# Hardware configuration
The harware could be configured using telnet to port 9999.

To change IP address select Choice 0 Server

Make sure that:
- the **CPU performance = High** in the ```Choice 1 Expert```
- the **Baudrate = 921600** in the ```Choice 1 Channel 1```.

The typical configuration telnet session:
```
telnet 192.168.50.10 9999
Trying 192.168.50.10...
Connected to 192.168.50.10.
Escape character is '^]'.

MAC address 0080A384B4EF
Software version V7.0.0.3 (210714) XPTEXE

Press Enter for Setup Mode 


*** basic parameters 
Hardware: Ethernet TPI
IP addr 192.168.50.10, gateway 192.168.50.1,netmask 255.255.255.0
DNS Server not set
DHCP FQDN option: Disabled

*** Security
SNMP is                    enabled
SNMP Community Name:       public
Telnet Setup is            enabled
TFTP Download is           enabled
Port 77FEh is              enabled
77FEh Access Mode is       Read & Write      
Web Server is              enabled
Web Setup is               enabled
ECHO is                    disabled
Enhanced Password is       enabled
Port 77F0h is              enabled
Telnet Authentication is   disabled

*** Channel 1
Baudrate 921600, I/F Mode 4C, Flow 00
Port 10001
Connect Mode : C0
Send '+++' in Modem Mode enabled
Show IP addr after 'RING' enabled
Auto increment source port disabled
Remote IP Adr: --- none ---, Port 00000
Disconn Mode : 00
Flush   Mode : 00

*** Expert
TCP Keepalive    : 45s
ARP cache timeout: 600s
CPU performance: High
Monitor Mode @ bootup : enabled
RS485 tx enable  : active low
HTTP Port Number : 80
SMTP Port Number : 25
MTU Size: 1400
TCP Re-transmission timeout: 500 ms
Alternate MAC: disabled
Ethernet connection type: auto-negotiate

*** E-mail
Mail server: 0.0.0.0
Unit       : 
Domain     : 
Recipient 1: 
Recipient 2: 

- Trigger 1 
Serial trigger input: disabled
  Channel: 1
  Match: 00,00
Trigger input1: X
Trigger input2: X
Trigger input3: X
Message : 
Priority: L
Min. notification interval: 1 s
Re-notification interval  : 0 s

- Trigger 2 
Serial trigger input: disabled
  Channel: 1
  Match: 00,00
Trigger input1: X
Trigger input2: X
Trigger input3: X
Message : 
Priority: L
Min. notification interval: 1 s
Re-notification interval  : 0 s

- Trigger 3 
Serial trigger input: disabled
  Channel: 1
  Match: 00,00
Trigger input1: X
Trigger input2: X
Trigger input3: X
Message : 
Priority: L
Min. notification interval: 1 s
Re-notification interval  : 0 s


Change Setup:
  0 Server
  1 Channel 1
  3 E-mail
  5 Expert
  6 Security
  7 Defaults
  8 Exit without save
```
  9 Save and exit            Your choice ? 
