# Socket-programming
依序用python實做了TCP、TCP+UDP、Time-out、multiport、和p2p系統，並增設了GUI

各branch功能:

TCP:用TCP在本地傳送訊息，且實作當訊息長度過長時，系統如何將訊息適當拆解並重建且接收端能正確解讀。

TCP+UDP:在本地可同時使用TCP和UDP兩種傳輸，且新增加密功能，訊息再傳輸前會先雜湊，接收方在解密。

Timeout and Multiport:新增Timeout功能防止長時間連線失敗大量占用網路，且可讓server一對多連線。

p2p:整合前面功能的p2p系統。
