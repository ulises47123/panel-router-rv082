# RV082 (fw 2.0.0.19-tm): especificación de lectura y guardado por HTTP
## Reenvío de puertos, Port Triggering, Service Management, UPnP, DMZ, Firewall general, Access Rules y Content Filter

Fuentes analizadas:
- `exploracion/crudo/`: adv_forwarding.htm, adv_upnp.htm, adv_dmz.htm, f_general.htm, access_rules.htm, content_filter.htm, nk.js, lg.js
- `exploracion/crudo_extra/`: páginas que bajé con GET de solo lectura: `service0.htm`, `service1.htm`, `edit_access_rules.htm`, `PortRange_table.htm`, `UPnP_table.htm`, `nk20090220151520.js`, `lg20090220151520.js`. Las páginas cargan los JS con fecha en el nombre (`nk20090220151520.js`), pero son **idénticos byte a byte** a `nk.js` y `lg.js`.

No hice ningún POST ni toqué nada del router.

---

## 0. Reglas generales (valen para todas las páginas)

1. **Autenticación**: HTTP Basic (`admin:admin`) en cada request. No vi cookies de sesión.
2. **Envío**: todas las páginas guardan con `F.submit()` hecho por JS (los links "Save Settings" son `javascript: chSubmit(...)`). `F.submit()` **no dispara `onSubmit`**, así que validaciones como el `onSubmit` de DMZ no corren. Siempre `method="post"`, `Content-Type: application/x-www-form-urlencoded`, `action` = la misma página (`adv_forwarding.htm`, etc.). El charset de la página es `iso-8859-1`.
3. **Qué manda el navegador** (es lo que hay que imitar):
   - Todos los `<input type=hidden>` y `text` del form, **incluso vacíos** (`V_ip4=`).
   - Radios: solo el marcado. Checkbox: solo si está marcado (`name=value`); si no, **el campo no va**.
   - `<select>` común: el value de la opción seleccionada; si ninguna tiene `selected`, va la primera.
   - `<select multiple>`: una pareja `name=value` **por cada opción seleccionada, repetida**. Las listas se mandan así.
   - Controles `disabled`: **no se mandan**. Esto importa en f_general, en los horarios y en las páginas con JS en `onLoad` que deshabilita campos.
   - `<input type=button>`: nunca se manda.
   - Hay que respetar el **orden del documento** (usar una lista de tuplas, no un dict).
   - Lo que está dentro de `<!-- ... -->` no existe para el navegador. Varias secciones (dominios, keywords, horarios, trusted domains) llegan comentadas cuando están apagadas.
   - Cada página tiene además un form `formdualwan` (solo `dualwanEnabled`, y en f_general también `firewall0`). Es un form **aparte** y no se manda.
4. **Inversión de listas (comportamiento raro, pero es lo que hace el navegador)**: antes de enviar, `selAll(s)` llama a `exPosion(s)`, que **invierte el orden** de las opciones, y después las selecciona todas. El POST lleva las entradas **en orden inverso** al que se ven en la página (la última agregada va primera). Pasa en adv_forwarding, adv_upnp, service0/1, f_general (trusted domains) y content_filter.
5. **Las listas se mandan completas cada vez.** No hay "agregar" ni "borrar" en el servidor: cada guardado reemplaza la lista entera. Para borrar se manda la lista sin esa entrada. **Si el programa no logra leer la lista actual y manda la lista vacía, el router borra todas las entradas.** Conviene que el parser falle de forma ruidosa y no siga en ese caso.
6. **`submitStatus`**: `1` = guardar; `0` = "falseSubmit", o sea volver a dibujar la página con el estado nuevo de un checkbox sin guardar (se usa para mostrar u ocultar secciones). En access_rules el campo hace de selector de acción (ver §6).
7. Hidden con espacio inicial: varios valores son `' checked'` (con espacio). El navegador los manda como `+checked`. Hay que copiarlos **tal cual se leyeron**.
8. Codificación: el navegador codifica `{`→`%7B`, `}`→`%7D`, `;`→`%3B`, espacio→`+`, `<`→`%3C`, `&`→`%26`. `urllib.parse.urlencode(lista_de_tuplas)` de Python da un resultado equivalente (deja `~` sin codificar; el servidor lo decodifica igual).
9. Recomendación: mandar `Referer: http://192.168.1.1/<pagina>` como haría el navegador. No vi que se controle, pero no cuesta nada.
10. **Verificación**: después de cada POST, hacer GET de la página y volver a parsear para confirmar. Las tablas emergentes `PortRange_table.htm`, `PortTrigger_table.htm` y `UPnP_table.htm` (solo lectura) también muestran lo que quedó aplicado.

### Cómo leer el HTML (para todas las páginas)
- Hidden: `<input type=hidden name="X" value='...'>`. El value puede venir con comillas simples o dobles. **Ojo con `service_menu`**: su value (entre comillas simples) contiene HTML con comillas dobles y `&` sin escapar (`TCP&UDP`). Conviene tomar el texto crudo entre `value='` y la `'` que cierra, y no pasarlo por un des-escapado de entidades.
- Listas: `<select multiple name="PortRangeList" ...> <option value="...">texto</option> ... </select>`. En las copias actuales **todas las listas están vacías** (no hay reglas cargadas), así que no vi cómo las dibuja el servidor. Como el JS (`showList`) parsea el `value` con el formato que se describe abajo, el servidor tiene que dibujar el `value` en ese mismo formato. Hay que confirmarlo con la primera regla real.

---

## 1. adv_forwarding.htm: Port Range Forwarding + Port Triggering

### 1.1 Form
`<form name="formForwarding" method="post" action="adv_forwarding.htm">`

Campos en orden de documento:

| # | name | tipo | valor actual / notas |
|---|---|---|---|
| 1 | lanIP1 | hidden | `192` |
| 2 | lanIP2 | hidden | `168` |
| 3 | lanIP3 | hidden | `1` |
| 4 | page | hidden | `adv_forwarding.htm` |
| 5 | submitStatus | hidden | `1` |
| 6 | service_menu | hidden | catálogo de servicios en HTML (ver 1.2) |
| 7 | V_protocol | select | servicio del editor; tras "Add to list" vuelve a la opción 0 = `16777216` |
| 8 | V_ip4 | text | último octeto del editor; queda `""` tras agregar |
| 9 | V_valid | checkbox value=1 | queda desmarcado tras agregar, así que **no va** |
| 10 | PortRangeList | select multiple | **lista de reenvíos** (repetido, invertido) |
| 11 | ApName | text | editor de trigger, `""` |
| 12 | oBegPrt | text | `""` |
| 13 | oEndPrt | text | `""` |
| 14 | iBegPrt | text | `""` |
| 15 | iEndPrt | text | `""` |
| 16 | PortTriggerList | select multiple | **lista de triggers** (repetido, invertido) |

Botones (`sM`, `addPortRangeApplication`, `deletePortRangeApplication`, `showNew1`, etc.) no se mandan.

### 1.2 Servicios y códigos (`service_menu` / `V_protocol`)
`service_menu` (hidden) trae `<option value="ID">Nombre [PROTO/ini~fin]</option>...`. Valores actuales:

| ID | hex | Servicio |
|---|---|---|
| 16777216 | 0x01000000 | All Traffic [TCP&UDP/1~65535] |
| 16777217 | 0x01000001 | DNS [UDP/53] |
| 16777218 | 0x01000002 | FTP [TCP/21] |
| 16777219 | 0x01000003 | HTTP [TCP/80] |
| 16777220 | 0x01000004 | HTTP Secondary [TCP/8080] |
| 16777221 | 0x01000005 | HTTPS [TCP/443] |
| 16777222 | 0x01000006 | HTTPS Secondary [TCP/8443] |
| 16777223 | 0x01000007 | TFTP [UDP/69] |
| 16777224 | 0x01000008 | IMAP [TCP/143] |
| 16777225 | 0x01000009 | NNTP [TCP/119] |
| 16777226 | 0x0100000A | Ping [ICMP] (solo aparece en edit_access_rules) |
| 16777227 | 0x0100000B | POP3 [TCP/110] |
| 16777228 | 0x0100000C | SNMP [UDP/161] |
| 16777229 | 0x0100000D | SMTP [TCP/25] |
| 16777230 | 0x0100000E | TELNET [TCP/23] |
| 16777231 | 0x0100000F | TELNET Secondary [TCP/8023] |
| 16777232 | 0x01000010 | TELNETSSL [TCP/992] |
| 16777233 | 0x01000011 | DHCP [UDP/67] |
| 16777234 | 0x01000012 | L2TP [UDP/1701] |
| 16777235 | 0x01000013 | Not Check Port [TCP&UDP/0~0] |
| 16777236 | 0x01000014 | ESP [ESP] (proto 50) |
| 16777237 | 0x01000015 | GRE [GRE] (proto 47) |
| 134217728 | 0x08000000 | PPTP [TCP/1723] |
| 134217729 | 0x08000001 | IPSec [UDP/500] |

- Los IDs son **identificadores opacos** que asigna el router: byte alto = familia (0x01 predefinidos, 0x08 passthrough VPN) y byte bajo = índice. Los servicios **creados por el usuario** reciben un ID del servidor (en `service0.htm` el JS considera "predefinido, no borrable" todo ID con `0 < id < 0x9000000`; en `service1.htm` el límite es `< 0x2000000`). Supongo que los IDs de usuario serán ≥ 0x9000000 (150994944), **pero no lo pude comprobar**: hay que crear el servicio y después leer su ID en el `service_menu` del GET siguiente.
- El `<select V_protocol>` se arma con `document.write`: la primera opción (All Traffic) va siempre y del resto solo las que tienen protocolo exactamente `TCP` o `UDP`. Quedan afuera **Not Check Port, ESP y GRE**; PPTP e IPSec sí aparecen. (El script empieza con `outputer` sin definir y escribe la palabra "undefined" antes del primer `<option>`. Es texto suelto dentro del select, el navegador lo ignora.)
- **Solo se puede usar un servicio por puerto** del lado WAN, con el mismo puerto interno: no hay traducción de puertos en esta página (eso existe solo en UPnP).
- Un mismo servicio **no puede estar dos veces** en la lista (`ckService`: "This Service was already in the list"), así que no se puede mandar el mismo servicio a dos IPs.
- Máximo **30** reenvíos y **30** triggers.

### 1.3 Formato de cada entrada
**PortRangeList**: `value = "<serviceID>{<octeto4>;<enable>}"`
- `octeto4` = 1..254 (validado con `IP1to254Check` y normalizado con `parseInt`). La IP completa es `lanIP1.lanIP2.lanIP3.octeto4`.
- `enable` = `1` (casilla Enable marcada) o `0`.
- Texto mostrado (no se manda): `"<texto del servicio>-><lan1>.<lan2>.<lan3>.<oct4>"`, p. ej. `HTTP Secondary [TCP/8080~8080]->192.168.1.50`.
- Ejemplo: `16777220{50;1}`.

**PortTriggerList**: `value = "<ApName>{<sID>;<trigIni>~<trigFin>;<inIni>~<inFin>}"`
- `sID` = `0` para una entrada nueva. Al editar se conserva el ID que trajo el servidor.
- El JS ordena cada par (si fin < ini, los intercambia), valida 0..65535 y rechaza que se solapen con otras entradas tanto los rangos de trigger como los de entrada.
- ApName: máximo 12 caracteres. Mejor evitar `{ } ; ~`.
- Texto mostrado: `Nombre[6000~6010;7000~7010]`.
- Ejemplo: `Juego{0;6000~6010;7000~7010}`.

### 1.4 Guardar
`Save Settings` → `chSubmit(formForwarding)`:
```
selAll(PortRangeList)     // invierte el orden y selecciona todo
selAll(PortTriggerList)   // ídem
F.submit()                // POST a adv_forwarding.htm, submitStatus=1
```
No recalcula ningún hidden. Las validaciones están solo en "Add to list" (IP 1-254, puertos, duplicados, límite de 30).

### 1.5 Ejemplo A: agregar TCP 8080 → 192.168.1.50 (habilitado), con la lista vacía
TCP 8080 ya existe como servicio predefinido "HTTP Secondary" = `16777220`.
```
POST /adv_forwarding.htm
lanIP1=192
lanIP2=168
lanIP3=1
page=adv_forwarding.htm
submitStatus=1
service_menu=<texto crudo leído, sin modificar>
V_protocol=16777216
V_ip4=
PortRangeList=16777220{50;1}
ApName=
oBegPrt=
oEndPrt=
iBegPrt=
iEndPrt=
```
Cuerpo codificado (con service_menu abreviado):
```
lanIP1=192&lanIP2=168&lanIP3=1&page=adv_forwarding.htm&submitStatus=1&service_menu=%3Coption+value%3D%2216777216%22%3EAll+Traffic+%5BTCP%26UDP%2F1~65535%5D%3C%2Foption%3E...&V_protocol=16777216&V_ip4=&PortRangeList=16777220%7B50%3B1%7D&ApName=&oBegPrt=&oEndPrt=&iBegPrt=&iEndPrt=
```
Como la lista de triggers está vacía, `PortTriggerList` no va.

Si ya había entradas, por ejemplo las visibles [E1, E2], el navegador agrega la nueva al final ([E1, E2, NEW]) y manda `PortRangeList=NEW&PortRangeList=E2&PortRangeList=E1`. Los triggers existentes también hay que mandarlos (invertidos); si no, se borran.

### 1.6 Ejemplo B: borrar ese reenvío
Mismo POST con la lista sin esa entrada. Si era la única, el campo `PortRangeList` **no va**:
```
lanIP1=192&lanIP2=168&lanIP3=1&page=adv_forwarding.htm&submitStatus=1&service_menu=...&V_protocol=16777216&V_ip4=&ApName=&oBegPrt=&oEndPrt=&iBegPrt=&iEndPrt=
```
Para desactivarlo sin borrarlo: `PortRangeList=16777220{50;0}`.

### 1.7 Ejemplo C: trigger nuevo
```
...&ApName=&oBegPrt=&oEndPrt=&iBegPrt=&iEndPrt=&PortTriggerList=Juego%7B0%3B6000~6010%3B7000~7010%7D
```

### 1.8 Crear un servicio nuevo (Service Management → `service0.htm`)
El botón "Service Management" abre `service0.htm` en una ventana aparte. La misma página sirve para adv_forwarding y para edit_access_rules (`openService()`).

Form: `<form name="formservice" method="post" action="service0.htm">`

| name | tipo | valor |
|---|---|---|
| upnpOpen | hidden | `0` |
| service_menu | hidden | `<option value="Nombre{ID;proto;ini;fin;0}">Nombre [TCP/ini~fin]</option>...` (formato **distinto** al de adv_forwarding: el value lleva todo) |
| PortRangeList | select multiple | **lista de servicios** |
| V_name | text (max 11) | `""` tras agregar |
| V_protocol | select | `6`=TCP, `17`=UDP; tras agregar vuelve a `6` |
| V_portS | text | `""` |
| V_portE | text | `""` |

(En service0 no existe `Vpint`: solo se escribe con document.write si `upnpOpen=="1"`.)

Formato de cada servicio en la lista: `"<Nombre>{<ID>;<proto>;<ini>;<fin>;<puertoInterno>}"`
- Nuevo: `ID=0` y `puertoInterno=0` (en service0). Ejemplo: `SoftEther{0;6;5555;5555;0}`.
- proto: 6=TCP, 17=UDP (el editor solo ofrece estos dos; los predefinidos también usan 0, 50 y 47).
- El JS invierte ini/fin si vienen al revés, valida 1..65535 y admite hasta 100 servicios.

**Rareza importante**: la lista visible de `service0.htm` **omite el primer servicio (All Traffic)** y también los que no son TCP/UDP (**Not Check Port, ESP, GRE**), porque el script se saltea el primer `</option>` y filtra por protocolo. El navegador **nunca manda esos servicios**. El servidor tiene que ignorar la ausencia de los predefinidos; hay que imitarlo igual, sin agregarlos.

Lista que manda el navegador hoy (orden visible): DNS, FTP, HTTP, HTTP Secondary, HTTPS, HTTPS Secondary, TFTP, IMAP, NNTP, POP3, SNMP, SMTP, TELNET, TELNET Secondary, TELNETSSL, DHCP, L2TP, PPTP, IPSec, [servicios de usuario TCP/UDP], y el nuevo al final. Todo eso **invertido** en el POST.

Ejemplo: crear "SoftEther" TCP 5555-5555:
```
POST /service0.htm
upnpOpen=0
service_menu=<crudo>
PortRangeList=SoftEther{0;6;5555;5555;0}
PortRangeList=IPSec{134217729;17;500;500;0}
PortRangeList=PPTP{134217728;6;1723;1723;0}
PortRangeList=L2TP{16777234;17;1701;1701;0}
PortRangeList=DHCP{16777233;17;67;67;0}
PortRangeList=TELNETSSL{16777232;6;992;992;0}
PortRangeList=TELNET Secondary{16777231;6;8023;8023;0}
PortRangeList=TELNET{16777230;6;23;23;0}
PortRangeList=SMTP{16777229;6;25;25;0}
PortRangeList=SNMP{16777228;17;161;161;0}
PortRangeList=POP3{16777227;6;110;110;0}
PortRangeList=NNTP{16777225;6;119;119;0}
PortRangeList=IMAP{16777224;6;143;143;0}
PortRangeList=TFTP{16777223;17;69;69;0}
PortRangeList=HTTPS Secondary{16777222;6;8443;8443;0}
PortRangeList=HTTPS{16777221;6;443;443;0}
PortRangeList=HTTP Secondary{16777220;6;8080;8080;0}
PortRangeList=HTTP{16777219;6;80;80;0}
PortRangeList=FTP{16777218;6;21;21;0}
PortRangeList=DNS{16777217;17;53;53;0}
V_name=
V_protocol=6
V_portS=
V_portE=
```
Para borrar un servicio de usuario: mismo POST sin esa entrada. Para editarlo: se conserva su ID y se cambian los demás campos. Los predefinidos no se pueden editar ni borrar (el JS desactiva los botones).

Qué hace el navegador después: `chSubmit` de service0 llama a `opener.closeService()`. Al segundo cierra la ventana y **a los 3 s re-guarda la página madre** (`refreshMe`): en adv_forwarding hace `chSubmit(formForwarding)` con submitStatus=1, que es un guardado normal del estado que esté en pantalla; en edit_access_rules hace un POST con submitStatus=0 (solo recarga). Para imitarlo: después del POST a service0, hacer GET de adv_forwarding.htm y volver a mandarlo sin cambios. Es inofensivo, porque manda la misma lista. Después leer en el `service_menu` nuevo el ID asignado a "SoftEther" y recién ahí usarlo en `PortRangeList=<ID>{50;1}`.

---

## 2. adv_upnp.htm: UPnP

### 2.1 Form
`<form name="formUpnp" method="post" action="adv_upnp.htm">`

| # | name | tipo | valor actual |
|---|---|---|---|
| 1 | page | hidden | `adv_upnp.htm` |
| 2 | submitStatus | hidden | `1` |
| 3 | lanIP1 / lanIP2 / lanIP3 | hidden | `192` / `168` / `1` |
| 4 | service_menu | hidden | catálogo UPnP (formato `Nombre [UDP/53->53]`; **sin** All Traffic, PPTP ni IPSec) |
| 5 | UPnP_Work | radio | `1`=Sí, `0`=No (**actual: 0**) |
| 6 | V2_protocol | select | primera opción = `16777217` (DNS) |
| 7 | V2_ip4 | text (max 20) | "Name or IP Address" completo; `""` |
| 8 | V2_valid | checkbox value=1 | desmarcado, no va |
| 9 | UPnPList | select multiple | lista de reenvíos UPnP estáticos (vacía) |

V2_protocol: el `document.write` no hace caso especial de la primera opción y filtra TCP/UDP, así que quedan DNS…L2TP (sin Not Check Port, ESP ni GRE).

### 2.2 Formato de entrada UPnPList
`value = "<serviceID>{<IP o nombre>;<enable>}"`. Ejemplo: `16777219{192.168.1.50;1}`. A diferencia de forwarding, acá va la **IP completa** o un nombre (`showList` usa `indexOf("{")` y `lastIndexOf(";")`). Texto: `HTTP [TCP/80->80]->192.168.1.50`. Máximo 30 entradas y sin servicios repetidos.

Los servicios UPnP se manejan en `service1.htm` (`upnpOpen=1`). Es otra lista, que incluye puerto externo → interno: `"Nombre{ID;proto;ext;ext;int}"`. No existe `V_portE`; `addtoList` pasa `V_portS` como ini y como fin. Campos: `upnpOpen=1, service_menu, PortRangeList..., V_name, V_protocol, V_portS, Vpint`. Igual que service0, la lista visible **se saltea el primer servicio** (en service1 el primero es DNS: rareza o bug) y los que no son TCP/UDP. El límite de "predefinido" en service1 es ID < 0x2000000.

### 2.3 Guardar
`chSubmit(formUpnp)`: `selAll(UPnPList)` (invierte) → submit.

### 2.4 Ejemplos
Activar UPnP (lista vacía):
```
page=adv_upnp.htm&submitStatus=1&lanIP1=192&lanIP2=168&lanIP3=1&service_menu=<crudo>&UPnP_Work=1&V2_protocol=16777217&V2_ip4=
```
Desactivar: lo mismo con `UPnP_Work=0`. **Siempre hay que reenviar la UPnPList actual**; si no, se borra.

---

## 3. adv_dmz.htm: DMZ Host

### 3.1 Form
`<form name="formDMZ" method="post" action="adv_dmz.htm" onSubmit="IP0to254Check(this.dmzAddr4)">` (el `onSubmit` no corre con `F.submit()`).

| name | tipo | valor actual |
|---|---|---|
| page | hidden | `adv_dmz.htm` |
| submitStatus | hidden | `1` |
| statusconnectDMZ | hidden | `1` |
| pointbufList | hidden | `0` |
| status_netMask | hidden | `255.255.255.0` |
| dmzAddr1 / 2 / 3 | hidden | `192` / `168` / `1` |
| dmzAddr4 | text | `0` = **DMZ host desactivado** |

`chSubmit` no recalcula nada. La validación es solo `onBlur`: 0..254.

### 3.2 Ejemplos
Poner DMZ host 192.168.1.50:
```
page=adv_dmz.htm&submitStatus=1&statusconnectDMZ=1&pointbufList=0&status_netMask=255.255.255.0&dmzAddr1=192&dmzAddr2=168&dmzAddr3=1&dmzAddr4=50
```
Quitarlo: igual con `dmzAddr4=0`.

Nota: "DMZ host" (exponer una IP de la LAN) es otra cosa que el **puerto DMZ** físico que el equipo tiene activo (modo WAN1 + DMZ). `statusconnectDMZ` y `pointbufList` se copian tal cual se leyeron.

---

## 4. f_general.htm: Firewall general

### 4.1 Form
`<form name="formf_general" method="post" action="f_general.htm">`. En orden de documento (✔ = valor actual):

| name | tipo | valores |
|---|---|---|
| page | hidden | `f_general.htm` |
| submitStatus | hidden | `1` |
| **adPassword** | hidden | `admin` ← **la clave de admin en texto plano** |
| firewall | radio | `1` ✔ / `0` |
| spi | radio | `1` ✔ / `0` |
| spi0 | hidden | `' checked'` (estado guardado de spi=1; `''` si estaba en 0) |
| dos | radio | `1` ✔ / `0` |
| dos0 | hidden | `' checked'` |
| blockWANReq | radio | `1` ✔ / `0` |
| blockWANReq0 | hidden | `' checked'` |
| remoteMng | radio (value 1) | |
| remoteMng_h | hidden | `''` (va **entre** los dos radios remoteMng) |
| remoteMng | radio (value 0) | `0` ✔ |
| rmPort | text | `80` (**disabled** mientras remoteMng=0, así que no va) |
| remoteMng0 | hidden | `''` |
| port443 | hidden | `''` (lista `ini:fin:ini:fin...` de puertos ya reenviados) |
| rmPort_db | hidden | `80` |
| https | radio (1) | `1` ✔ |
| https_h | hidden | `' checked'` |
| https | radio (0) | |
| passMulti | radio | `1` / `0` ✔ |
| blockJava | checkbox =1 | no |
| blockCookies | checkbox =1 | no |
| blockActiveX | checkbox =1 | no |
| blockProxy | checkbox =1 | no |
| noblockTrusted | checkbox =1 | ver 4.3 |
| forbiddenURLs_add / local_forbiddenURLs_del | text / select multiple | **solo si la sección Trusted Domains está visible** (hoy viene comentada) |

Los hidden `*0` y `*_h` son el estado guardado: el JS los usa para restaurar los radios al volver a activar el firewall. Hay que mandarlos **tal cual se leyeron**.

### 4.2 JS de `onLoad` (cambia qué campos se mandan)
`onLoad="chDismatch(); chDMZ(); chSH(); chTrust();"`
- `chDismatch`: `noblockTrusted.checked = (existe local_forbiddenURLs_del)`. El estado de la casilla se deduce de si la sección de Trusted Domains vino sin comentar.
- `chDMZ`: si firewall=0, `disable_FW()`.
- `chSH`: si firewall=0 o remoteMng=0, **rmPort queda disabled y no se manda**. Solo va cuando remoteMng=1 y firewall=1.
- `chTrust`: si los 4 bloqueos (Java/Cookies/ActiveX/Proxy) están apagados, `noblockTrusted` queda desmarcado y **disabled**, así que no va. Si además la lista de trusted existía, hace `falseSubmit` para ocultarla.

### 4.3 Guardar (`chSubmit`)
1. Si firewall=0: `rmPort.disabled=true`.
2. Si remoteMng=1: revisa que `rmPort` no caiga dentro de un rango de `port443`. Si choca, muestra un alerta y **cancela**. Si no choca, puede mostrar un aviso ("use https://x.x.x.x:puerto").
3. Si existe `local_forbiddenURLs_del`: `selAll` (invierte).
4. `submitStatus=1` → submit.

Protecciones del navegador porque la clave es "admin" (`adPassword=="admin"`):
- `disable_FW1()`: **no permite desactivar el firewall** (vuelve a marcar Enable y ofrece ir a password.htm).
- `chSH1()`: **no permite activar Remote Management**.
El servidor quizás no las controla, pero un programa que imite al navegador **tampoco debería hacerlo** mientras la clave sea admin.

Si el firewall se desactiva (con la clave ya cambiada), `disable_FW()` deja spi=0, dos=0, blockWANReq=0 y **remoteMng=1 (Enable)**, y después **deshabilita** todos esos radios y rmPort. El POST lleva entonces solo `firewall=0` y los hidden: no van spi, dos, blockWANReq, remoteMng ni rmPort. Según la ayuda, desactivar el firewall **activa la administración remota y apaga Access Rules y Content Filter**.

Trusted Domains: al marcar `noblockTrusted` (requiere que haya algún bloqueo marcado) se hace `falseSubmit`: `submitStatus=0`, `action="f_general.htm#1"`, POST. El servidor devuelve la página con la sección sin comentar (`forbiddenURLs_add` max 23 caracteres, `local_forbiddenURLs_del` con hasta 50 dominios, cada opción con value = texto = dominio). Después se guarda con submitStatus=1 y la lista invertida.

### 4.4 Ejemplos
Guardar sin cambios (estado actual), lo que manda el navegador:
```
page=f_general.htm&submitStatus=1&adPassword=admin&firewall=1&spi=1&spi0=+checked&dos=1&dos0=+checked&blockWANReq=1&blockWANReq0=+checked&remoteMng_h=&remoteMng=0&remoteMng0=&port443=&rmPort_db=80&https=1&https_h=+checked&passMulti=0
```
Desactivar SPI y DoS: cambiar `spi=0`, `dos=0` y dejar los hidden `spi0`/`dos0` como se leyeron.

Bloquear Java y Cookies: agregar al final `&blockJava=1&blockCookies=1`. noblockTrusted queda habilitada pero desmarcada, así que no va.

Desactivar "Block WAN Request" (que responda ping desde la WAN): `blockWANReq=0`.

Multicast pass-through: `passMulti=1`.

Remote management en 8443 (solo con la clave cambiada; ver riesgos):
```
...&blockWANReq0=+checked&remoteMng=1&remoteMng_h=&rmPort=8443&remoteMng0=&port443=&rmPort_db=80&https=1&https_h=+checked&passMulti=0
```
(El orden exacto: el radio `remoteMng=1` va **antes** de `remoteMng_h`, y `rmPort` va después de `remoteMng_h`.)

---

## 5. Access Rules: `access_rules.htm` (lista) + `edit_access_rules.htm` (agregar/editar)

### 5.1 Lectura de access_rules.htm
Form `formaccess_rules`, `action="access_rules.htm"`. Hidden:
```
page=access_rules.htm  submitStatus=0  ReqPage=0  ChangeEntry=0  ChangePolicy=0
EnableLine=0  DisableLine=0  EditLine=0  RemoveLine=0
thisPage=1  totalPage=1  totalRules=3  AfterRemove=0  submitClick=0
```
Más `JumpPage` (select; su opción no tiene value, así que se manda el texto `1`) y `perPage` (`0`=5, `1`=10, `2`=20, `3`=40 por página; actual `0`).

Las reglas **no** vienen en JS ni en hidden: vienen como **filas de tabla HTML** (`<tr>` con celdas Priority, Enable, Action, Service, Source Interface, Source, Destination, Time, Day, editar, Delete). Hoy solo están las 3 predefinidas, que no se pueden editar (sin prioridad, checkbox `disabled` sin name, sin links):
1. Allow · All Traffic [1] · LAN · Any → Any · Always
2. Deny · All Traffic [1] · WAN · Any → Any · Always
3. Deny · All Traffic [1] · DMZ · Any → Any · Always

Las reglas de usuario (no hay ninguna todavía) seguramente traen un `<select>` de prioridad con `onChange="changePolicy(this, e, p)"`, un checkbox con `onClick="enableLine(this, e)"`, un link `editLine(n)` y otro `removeLine(n)`. **El formato exacto de esas filas no lo pude ver.** Con la primera regla creada hay que hacer GET y mirar los números `n`/`e` (es probable que sean el número de prioridad) y si esos controles tienen `name` (si lo tienen, también entran en el POST). Hay paginación: con `perPage=3` (40) se ven todas en una página (máx. 50 reglas).

Acciones (todas son POST a access_rules.htm con todos los hidden; cambia solo lo indicado):

| Acción | Función | Campos que cambian |
|---|---|---|
| Refrescar por página | perPageRefresh | `submitStatus=1`, `perPage=N` |
| Ir a página | reqPage(n) | `submitStatus=2`, `ReqPage=N` |
| Cambiar prioridad | changePolicy(s,e,p) | `submitStatus=3`, `ChangeEntry=e`, `ChangePolicy=p` |
| Habilitar/deshabilitar | enableLine(c,e) | `submitStatus=4`, `EnableLine=e` **o** `DisableLine=e` |
| Editar | editLine(n) | `submitStatus=5`, `EditLine=n` → el servidor responde con el editor cargado (`editRuleNo=n`) |
| Borrar | removeLine(n) | `submitStatus=6`, `RemoveLine=n`, `submitClick=1` |
| **Restaurar reglas por defecto** | defaultRules | `submitStatus=10` ← **borra todas las reglas de usuario** |

"Add New Rule" (`chTotalRules`): si totalRules ≥ 50 avisa; si no, hace **GET** de `edit_access_rules.htm`.

Después de borrar, el servidor devuelve `AfterRemove=1` y el `onLoad` (`afterRemove`) hace `location.replace("access_rules.htm")`, es decir, otro GET.

### 5.2 Ejemplo: borrar la regla n.º 4 (por ejemplo, la primera de usuario)
```
POST /access_rules.htm
page=access_rules.htm&submitStatus=6&ReqPage=0&ChangeEntry=0&ChangePolicy=0&EnableLine=0&DisableLine=0&EditLine=0&RemoveLine=4&thisPage=1&totalPage=1&totalRules=4&AfterRemove=0&submitClick=1&JumpPage=1&perPage=0
```
(+ los campos con name de las filas, si los hubiera, que hoy no se pueden ver.) Antes de mandarlo hay que confirmar con un GET qué número usa el link `removeLine(...)` de esa fila.

### 5.3 edit_access_rules.htm (página secundaria para agregar/editar)
`<form name="formedit_access_rules" method="post" action="edit_access_rules.htm">`. Campos en orden de documento:

| name | tipo | valores |
|---|---|---|
| editRuleNo | hidden | `0` = regla nueva; `n` = editar la regla n |
| service_menu | hidden | catálogo (incluye **Ping 16777226**; texto sin espacio antes de `[`) |
| page | hidden | `edit_access_rules.htm` |
| afterSubmit | hidden | `0` (el servidor responde 1 = "guardado, ¿agregar otra?"; 2 = volver) |
| submitStatus | hidden | `1` |
| **log** | hidden | `0` ← **hay DOS campos `log`** |
| totalRules | hidden | `3` |
| ruleAction | select | `1`=Allow (primera, por defecto), `2`=Deny |
| addRule_serviceID | select | ID de servicio. Se arma con la primera opción (All Traffic) más todas las que **no** tengan puertos `0~0` (quedan afuera Not Check Port, ESP y GRE; Ping, PPTP e IPSec sí están) |
| **log** | select | `1`=Log packets match this rule (primera, por defecto), `0`=Not log |
| addRule_srcEnet | select | `2`=LAN (por defecto), `1`=WAN, `3`=DMZ, `4`=Any |
| rSour | select | `1`=Any, `2`=Single (por defecto), `3`=Range |
| srcipAddrb1..4 | text | IP origen (o inicio de rango) |
| srcipAdde1..4 | text | fin del rango origen |
| rDest | select | `1`=Any, `2`=Single (por defecto), `3`=Range |
| desipAddrb1..4 | text | IP destino |
| desipAdde1..4 | text | fin del rango destino |
| addRule_timeConstraint | select | `0`=always, `1`=from |
| addRule_timeBeginHour / Min, addRule_timeEndHour / Min | text | `HH`, `MM` con dos dígitos; **disabled si always** |
| days | checkbox | `7`=Everyday, `0`=Dom … `6`=Sáb; **disabled si always**; si se marca Everyday, los días 0-6 quedan disabled (va solo `days=7`) |

`chIPRange()` no hace nada (switch vacío): **los 16 campos de IP se mandan siempre**, vacíos o no, aunque sea Any.

`chSubmit()` (validación del navegador): con Single, los 4 octetos de inicio tienen que estar completos; con Range, inicio y fin; si timeConstraint=1, las 4 casillas de hora. Después `submit()`. Los octetos se validan 0..255 en `onBlur` y las horas se normalizan a 2 dígitos.

**Campo `log` duplicado**: el navegador manda `log=0` (hidden) **y** `log=<select>`. No sé cuál toma el servidor (casi seguro la primera o la última aparición). **Hay que mandar los dos, en ese orden.**

### 5.4 Ejemplo: agregar "Deny, All Traffic, LAN 192.168.1.60 → Any, siempre, con log"
```
POST /edit_access_rules.htm
editRuleNo=0
service_menu=<crudo>
page=edit_access_rules.htm
afterSubmit=0
submitStatus=1
log=0
totalRules=3
ruleAction=2
addRule_serviceID=16777216
log=1
addRule_srcEnet=2
rSour=2
srcipAddrb1=192&srcipAddrb2=168&srcipAddrb3=1&srcipAddrb4=60
srcipAdde1=&srcipAdde2=&srcipAdde3=&srcipAdde4=
rDest=1
desipAddrb1=&desipAddrb2=&desipAddrb3=&desipAddrb4=
desipAdde1=&desipAdde2=&desipAdde3=&desipAdde4=
addRule_timeConstraint=0
```
Con horario de lunes a viernes de 08:00 a 17:00, cambiar el final por:
```
addRule_timeConstraint=1&addRule_timeBeginHour=08&addRule_timeBeginMin=00&addRule_timeEndHour=17&addRule_timeEndMin=00&days=1&days=2&days=3&days=4&days=5
```
(Todos los días: `...&days=7` solo.)

Respuesta esperada: la misma página con `afterSubmit` = `'1'` (el navegador pregunta "¿agregar otra?") y `totalRules` incrementado. Confirmar después con GET de access_rules.htm.

Editar la regla n: (a) POST a access_rules.htm con `submitStatus=5&EditLine=n` (la respuesta es el editor cargado; leer de ahí todos los valores), (b) POST a edit_access_rules.htm con `editRuleNo=n` y los campos cambiados.

---

## 6. content_filter.htm: Content Filter

### 6.1 Form
`<form name="formcontent_filter1" method="post" action="content_filter.htm">`. En orden:

| name | tipo | valor actual |
|---|---|---|
| page | hidden | `content_filter.htm` |
| submitStatus | hidden | `1` |
| statustypeCF | hidden | `1` |
| pointbufList1 / 2 / 3 | hidden | `0` (en el HTML hay espacios **fuera** de la comilla; el valor es `0`) |
| forbiddenEnable | checkbox =1 | desmarcado. `onClick="falseSubmit"` |
| *(comentado si está apagado)* forbiddenURLs_add | text (max 31) | |
| *(comentado)* local_forbiddenURLs_del | select multiple | **dominios bloqueados**; value = texto = dominio |
| keywordsEnable | checkbox =1 | desmarcado. `onClick="falseSubmit"` |
| *(comentado)* keywords_add | text (max 23) | |
| *(comentado)* keywords_list | select multiple | **palabras clave**; value = texto |
| *(comentado)* rangeSchedule1 | select | `0`=always (actual), `1`=from |
| *(comentado)* TOD_startHour, TOD_startMin, TOD_endHour, TOD_endMin | text | disabled si always |
| *(comentado)* days | checkbox | `7`=Everyday, `0`..`6`; misma lógica que access rules |

`onLoad = chDismatch(); chSchedule();`. `chDismatch` marca `forbiddenEnable` si existe la lista de dominios y `keywordsEnable` si existe la de keywords. **El estado "activado" se deduce de si la sección vino sin comentar** en el HTML; no hay un atributo `checked`. Para leer el estado actual: ver si `local_forbiddenURLs_del` / `keywords_list` aparecen fuera de un comentario.

Límites: 50 dominios y 50 keywords. El JS rechaza duplicados exactos. sTrim quita los espacios de los bordes.

### 6.2 Flujo del navegador para bloquear un dominio (hoy todo está apagado)
**Paso 1, falseSubmit** (al tildar "Block Forbidden Domains"; no guarda, solo vuelve a dibujar con la sección abierta):
```
POST /content_filter.htm
page=content_filter.htm&submitStatus=0&statustypeCF=1&pointbufList1=0&pointbufList2=0&pointbufList3=0&forbiddenEnable=1
```
**Paso 2**: en la página devuelta aparecen `forbiddenURLs_add`, `local_forbiddenURLs_del` y seguramente la sección de horario. Leer esos campos de la respuesta (por ejemplo, si `rangeSchedule1` existe y qué valor trae).

**Paso 3, Save** (`chSubmit`: `selAll` de las dos listas si existen, `submitStatus=1`, submit):
```
POST /content_filter.htm
page=content_filter.htm&submitStatus=1&statustypeCF=1&pointbufList1=0&pointbufList2=0&pointbufList3=0&forbiddenEnable=1&forbiddenURLs_add=&local_forbiddenURLs_del=tiktok.com&local_forbiddenURLs_del=facebook.com&rangeSchedule1=0
```
(Si en pantalla quedó [facebook.com, tiktok.com], se manda invertido. Con `rangeSchedule1=0` los TOD_* y days están disabled y no van.)

Con horario de 08:00 a 12:00 todos los días: `...&rangeSchedule1=1&TOD_startHour=08&TOD_startMin=00&TOD_endHour=12&TOD_endMin=00&days=7`.

**Borrar un dominio**: Save igual sin ese dominio. Si se borra el último, `local_forbiddenURLs_del` no va, pero `forbiddenEnable=1` sigue (bloqueo activado con la lista vacía).

**Apagar el bloqueo de dominios**: falseSubmit **sin** `forbiddenEnable` (submitStatus=0) y después Save sin `forbiddenEnable` y sin la lista. No sé si el falseSubmit ya persiste el estado; por eso conviene hacer siempre los dos pasos como el navegador.

Keywords: igual con `keywordsEnable=1`, `keywords_add=` y `keywords_list=...` (invertida). Van después del bloque de dominios en el orden del documento.

---

## 7. Riesgos y qué no tocar

1. **Listas = reemplazo total.** En forwarding, triggers, UPnP, servicios, trusted domains, dominios y keywords, si se manda la lista vacía o incompleta, se borra lo demás. Parsear con cuidado y verificar con GET.
2. **f_general `adPassword`**: el HTML trae la clave de admin en texto plano. No guardarla en logs. Mandarla tal cual se leyó (el servidor probablemente la ignora, pero así lo hace el navegador).
3. **No desactivar el firewall** (`firewall=0`): activa la administración remota (Remote Management) desde la WAN y apaga Access Rules y Content Filter. Con la clave "admin" eso es acceso abierto desde Internet. El propio navegador lo impide mientras la clave sea admin.
4. **No activar Remote Management** con la clave admin (el navegador también lo bloquea). Si se activa, preferir HTTPS y un puerto que no esté reenviado (`port443`).
5. **Desactivar `https`** puede cortar el acceso de administración por 443. Hoy se administra por 80, pero la PC también vio 443/8080 abiertos.
6. **Access rules**: una regla `Deny` con origen LAN/Any y servicio All Traffic (o HTTP/HTTPS) que incluya la IP de la PC administradora puede **dejar al admin afuera** de la web del router. Las reglas de usuario tienen prioridad sobre las predefinidas (la "Allow LAN" es la última). Probar siempre con IP Single de una máquina de prueba, nunca con Any en LAN.
7. **`submitStatus=10` en access_rules = "Restore to Default Rules"**: borra todas las reglas de usuario. Nunca mandarlo por error. Por ejemplo, no reutilizar un form con submitStatus de una acción anterior; armar cada POST desde cero.
8. **DMZ host**: expone todos los puertos no reenviados de esa IP a Internet. Usar `dmzAddr4=0` para quitarlo.
9. **Port forwarding "All Traffic"** (16777216) hacia una IP equivale a un DMZ host. Forwardear 443/80/8080 puede chocar con la administración remota (f_general avisa si `rmPort` cae en un rango de `port443`).
10. **service0.htm**: no "completar" la lista con los predefinidos que el navegador no manda (All Traffic, Not Check Port, ESP, GRE), y no tocar IDs < 0x9000000. Cambiar un servicio usado por reglas de forwarding o de acceso cambia esas reglas.
11. UPnP_Work=1 permite que cualquier equipo de la LAN abra puertos solo. Con la VPN tipo VPN Azure no hace falta.
12. Nombres de servicios, apps y dominios: evitar `{ } ; ~ [ / ' "`, porque rompen los parsers de JS del propio router.

---

## 8. Dudas abiertas (verificar con la primera prueba real)
- Formato exacto de las `<option>` que dibuja el servidor en las listas: todas están vacías hoy. Se supone que el `value` es el mismo formato que arma el JS.
- ID que reciben los servicios creados por el usuario (¿≥ 0x9000000?).
- Si el servidor guarda las listas al revés: el navegador invierte en cada envío, así que se supone que el servidor vuelve a invertir al dibujar. Si no, el orden visual cambiaría en cada guardado. Para forwarding el orden no importa; para dominios tampoco.
- Cuál de los dos `log` toma edit_access_rules.
- HTML de las filas de reglas de usuario en access_rules.htm (names y números de `removeLine`/`editLine`/`changePolicy`).
- Si `submitStatus=0` (falseSubmit) en content_filter/f_general persiste algo o solo vuelve a dibujar.
- Respuesta HTTP de cada POST (código y si redirige). Se espera 200 con la página otra vez.

## 9. Esqueleto sugerido (Python)
```python
import re, urllib.parse, requests
S = requests.Session(); S.auth = ("admin", "admin")
B = "http://192.168.1.1/"

def hidden(html, name):
    m = re.search(r'name="?%s"?\s+value=(\'([^\']*)\'|"([^"]*)")' % re.escape(name), html)
    return (m.group(2) if m.group(2) is not None else m.group(3)) if m else None

def lista(html, name):   # opciones de un <select multiple> fuera de comentarios
    sin_coment = re.sub(r'<!--.*?-->', '', html, flags=re.S)
    m = re.search(r'<select multiple name="%s"[^>]*>(.*?)</select>' % name, sin_coment, re.S)
    if m is None: return None          # sección apagada o no existe
    return re.findall(r'<option[^>]*value="([^"]*)"', m.group(1))

def post(page, campos):              # campos = lista de tuplas en orden de documento
    body = urllib.parse.urlencode(campos, encoding="latin-1")
    return S.post(B + page, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded", "Referer": B + page})

# Agregar TCP 8080 -> .50
h = S.get(B + "adv_forwarding.htm").text
pr, pt = lista(h, "PortRangeList"), lista(h, "PortTriggerList")
assert pr is not None and pt is not None
pr = pr + ["16777220{50;1}"]
campos = [("lanIP1", hidden(h,"lanIP1")), ("lanIP2", hidden(h,"lanIP2")), ("lanIP3", hidden(h,"lanIP3")),
          ("page","adv_forwarding.htm"), ("submitStatus","1"), ("service_menu", hidden(h,"service_menu")),
          ("V_protocol","16777216"), ("V_ip4","")]
campos += [("PortRangeList", v) for v in reversed(pr)]
campos += [("ApName",""),("oBegPrt",""),("oEndPrt",""),("iBegPrt",""),("iEndPrt","")]
campos += [("PortTriggerList", v) for v in reversed(pt)]
# post("adv_forwarding.htm", campos); luego GET y verificar
```
