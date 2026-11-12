# RV082 (fw 2.0.0.19-tm): especificación de las páginas de red y DHCP

Páginas cubiertas: `network.htm`, `dhcp_setup.htm`, `dhcp_status.htm`, `lan_status.htm` y `home.htm`.

**Cómo se obtuvo.** Leí el HTML crudo de `exploracion/crudo/` junto con `nk.js` y `lg.js`. Comprobé que son idénticos byte a byte a `nk20090220151520.js` y `lg20090220151520.js`, que son los que las páginas cargan de verdad. Después cargué las copias locales en Chromium (Playwright) con **toda la red interceptada**, usando el host ficticio `router.invalid`, así que ningún paquete llegó al router. Ejecuté las funciones reales de "Save Settings" y **capturé el cuerpo exacto del POST** que arma el navegador.

Al router solo se le hicieron GET de lectura: los dos .js versionados, `dhcp_status.htm`, `Dhcp_table1.htm`, `lan_status.htm`, `home.htm`, `port8_information.htm` y `wan_port_information.htm`.

Los casos marcados **SIMULADO** usan una copia de la página editada a mano para imitar lo que el servidor devolvería en otro estado. Son tres: WAN en IP estática, WAN en PPPoE y listas DHCP con entradas. Hoy el router no está en ninguno de esos estados, así que su HTML real no se pudo ver.

---

## 0. Reglas generales (valen para todas las páginas)

1. **Autenticación**: HTTP Basic `admin:admin` en cada request. No hay cookies ni tokens CSRF.
2. **Envío**: `POST /<pagina>.htm` con `Content-Type: application/x-www-form-urlencoded`. Los espacios van como `+`, `=` como `%3D`, `>` como `%3E` y `@` como `%40`. Es lo mismo que `urllib.parse.urlencode` por defecto. La página declara charset `iso-8859-1`, así que conviene usar solo ASCII.
3. **El action lleva `#n` en algunos casos** (`network.htm#1`, `home.htm#1`). El fragmento no viaja, la URL efectiva es la misma.
4. **`submitStatus` decide si se guarda**:
   - `submitStatus=1` lo manda "Save Settings": guarda.
   - `submitStatus=0` lo manda `falseSubmit()`: el servidor solo **vuelve a dibujar** la página en otro modo, por ejemplo al cambiar el combo de tipo de WAN o el checkbox de DHCP.
   - Es inferencia: "Cancel Changes" es un simple GET que vuelve a lo guardado.
5. **El servidor COMENTA los bloques que no aplican.** Rodea con `<!-- ... -->` los bloques de los tipos de WAN no elegidos, el relay DHCP, etc. Dentro de esos comentarios hay `<input>` con los **mismos nombres** que los activos: `Wan1DnsA1` aparece 2 veces, `Wan1AliasIp1` 2 veces, `Wan1UserName` 2 veces. **Antes de parsear hay que quitar todos los comentarios HTML.** Si no, salen campos duplicados que el navegador nunca enviaría.
   - Los bloques comentados siguen trayendo los valores guardados. Sirven para *leer* la configuración de otros modos, pero no se envían.
6. **Reproducir lo que haría el navegador**:
   - Se omiten los controles `disabled` y los botones.
   - Checkbox y radio se envían solo si están marcados, con su `value`.
   - Un select simple envía la opción `selected`, o la primera si ninguna lo está.
   - Un select múltiple envía cada opción seleccionada como un par `nombre=valor` repetido.
   - El orden es el orden del documento.
7. **La parte peligrosa: el JS del `onLoad` y del Save modifica campos.** Si se reenvían tal cual los hidden del HTML crudo, se rompe la config. Las correcciones de cada página están abajo. En la sección 6 hay una implementación en Python validada contra el navegador, que da POST **idénticos byte a byte**.

---

## 1. `network.htm` (hostname, dominio, LAN, modo Dual-WAN/DMZ, tipo de WAN, DNS, MTU)

### 1.1 Cómo leer los valores actuales

Hay dos forms: `formdualwan` (solo el hidden `dualwanEnabled`, no se envía) y **`formNetwork`** (`action="network.htm" method="post"`). Todo lo siguiente está en `formNetwork`, **después de quitar los comentarios**.

| Dato | Dónde está | Valor hoy |
|---|---|---|
| Host Name | `<input name="hostname" maxlength=31>` | `TP-VPN` |
| Domain Name | `<input name="DomainName" maxlength=63>` | `soporte.com` |
| IP LAN | `ipAddr1..ipAddr4` (texto) y también el hidden `LanIp` (`'192.168.1.1'`) | 192.168.1.1 |
| Máscara LAN | `<select name="netMask">`. El value es el **último octeto**: `0`=255.255.255.0, `128`, `192`, `224`, `240`, `248`, `252`. También está el hidden `netMaskAll` | 0 (= /24) |
| MAC LAN | Texto `(MAC Address: xx-xx-xx-xx-xx-xx )` junto a "LAN Setting" | xx-xx-xx-xx-xx-xx |
| Modo | radio `wan_dmz`: `1`=Dual WAN, `0`=DMZ (el `checked` va en el tag) | `0` (DMZ) |
| Tipo WAN1 | `<select name="WAN1ConnectionType">`. **Ojo:** el atributo `selected` está en la línea siguiente dentro del tag `<option value="1"\n selected>` | `1` |
| DNS manual WAN1 (solo modo DHCP) | checkbox `setWan1DNS` (value 1) y `Wan1DnsA1..4`, `Wan1DnsB1..4` | sin marcar, 0.0.0.0 |
| MTU WAN1 | radio `mtu_auto1` (`1`=Auto, `0`=Manual) y `bytesMTU1` | Auto, 1500 |
| WAN2/DMZ | `WAN2ConnectionType` (hoy `2`), radio `DmzSubnetRange` (0=Subnet, 1=Range), `Wan2AliasIp1..4` y `Wan2AliasMaskIp1..4` (IP y máscara de la subred DMZ) | 0.0.0.0 |
| Info DHCP/PPTP (solo lectura) | hidden `dsDHCP1..4`, `deDHCP4`, `DhcpEnabled1` (`' checked'` o `''`), `dsPPTP1..4`, `dePPTP4`, `PPTPEnabled` (`' '`) | |
| Subred múltiple | checkbox `MLanSetting` **disabled** (se edita en `mlan.htm`). No se envía | |

Códigos de `WAN1ConnectionType` / `WAN2ConnectionType`:

| value | Tipo |
|---|---|
| 1 | Obtain an IP automatically (DHCP) |
| 2 | Static IP |
| 3 | PPPoE |
| 4 | PPTP |
| 7 | Transparent Bridge |
| 8 | Heart Beat Signal |

Desde JS (`chDismatch`), el tipo se deduce por **qué campos existen sin comentar**:

| Campos presentes | Tipo |
|---|---|
| `Wan1AliasIp1` y `Wan1UserName` | PPTP |
| solo `Wan1UserName` | PPPoE |
| `Wan1AliasIp1` y `wan1Bridge` | Bridge |
| solo `Wan1AliasIp1` | Static |
| `setWan1DNS` | DHCP |
| `Wan1HBSServer` | Heart Beat |

### 1.2 Qué hace "Save Settings" (`javascript:chSubmit(document.formNetwork)`)

Al cargar (`onLoad="chDismatch(); chsetDNS(); chDmzRange(); setDmzRange(); chDismatchLanMask(F); chSH1(); chSH2()"`):

- **`chDismatchLanMask`**: recalcula **`LanIp1..4`** partiendo `LanIp` por puntos y **`netMaskIp1..4`** partiendo `netMaskAll`. En el HTML crudo vienen **mal**: `LanIp1='196'`, `LanIp2..4=''` y `netMaskIp1..4=''`. Hay que reemplazarlos por `192,168,1,1` y `255,255,255,0`.
- **`chsetDNS`**:
  - Solo si WAN1 es DHCP. Si `setWan1DNS` está sin marcar, pone **`Wan1DnsNeq=1`** (en el crudo dice 0) y **deshabilita** `Wan1DnsA1..B4`, que entonces **no se envían**.
  - Si está marcado, `Wan1DnsNeq=0` y se envían los 8 campos. Lo mismo para WAN2 en modo Dual WAN.
  - Además llama a `onlyStatic()`, que en modo DMZ con WAN2=Static **deshabilita `WAN2ConnectionType`**.
- **`chSH1` / `chSH2`**: si MTU está en Auto, **deshabilita `bytesMTU1`**, que no se envía.

En `chSubmit(F)`:

1. Si la IP nueva es `127.0.0.1`, la rechaza.
2. Si PPTP está activo y la IP LAN cae en su rango, alerta y no guarda. Hoy PPTP no está activo.
3. Si `netMask.value != netMaskIp4` (cambiaste la máscara), muestra solo un aviso (`aChangedSubnet`).
4. Controles de Bridge y DMZ:
   - No se permiten dos Bridge a la vez.
   - Si DMZ en modo "Subnet" está en la misma /24 que la LAN, da error.
   - En Bridge, si `Wan1LanIp5 < Wan1LanIp4`, los intercambia.
5. DNS (DHCP con DNS manual o Static): si DNS1 es 0.0.0.0 y DNS2 no, **intercambia** (DNS2 pasa a DNS1 y DNS2 queda en 0). Si ambos son 0, avisa (`aNoDNS`) pero guarda igual.
6. Static WAN1: si algún campo de IP o gateway es distinto de 0, exige IP ≠ 0.0.0.0, máscara ≠ 0.0.0.0 y gateway ≠ 0.0.0.0. Lo mismo para WAN2 en Dual WAN.
7. **Rehabilita `WAN1ConnectionType` y `WAN2ConnectionType`**, para que se envíen aunque `onlyStatic` los hubiera deshabilitado. También rehabilita `Wan2DmzIp*`.
8. Si `ipAddr1..4` es distinto de `LanIp1..4`, aparece `confirm(cDeviceIP)`: "Device IP address has been modified…".
9. Pone `submitStatus=1` y hace `F.submit()`, un **POST a `/network.htm`**.

El cambio del combo de tipo de WAN, del radio Dual WAN/DMZ o de `DmzSubnetRange` llama a **`falseSubmit(F,n)`**. Esta función pone `submitStatus=0`, habilita los dos combos y hace POST a `network.htm#n`. El servidor responde con la página dibujada para el tipo nuevo (bloque descomentado) **sin guardar**, y después el usuario pulsa Save.

### 1.3 POST exacto de un guardado típico (capturado del navegador)

**N1: Save sin cambios, estado actual** (WAN1=DHCP, sin DNS manual, MTU Auto, modo DMZ):

```
POST /network.htm
page=network.htm&submitStatus=1&clickDualwan=0&clickDmz=0&LanIp=192.168.1.1&LanIp1=192&LanIp2=168&LanIp3=1&LanIp4=1&dsPPTP1=192&dsPPTP2=168&dsPPTP3=1&dsPPTP4=200&dePPTP4=204&dsDHCP1=192&dsDHCP2=168&dsDHCP3=1&dsDHCP4=100&deDHCP4=149&netMaskAll=255.255.255.0&netMaskIp1=255&netMaskIp2=255&netMaskIp3=255&netMaskIp4=0&DhcpEnabled1=+checked&PPTPEnabled=+&hostname=TP-VPN&DomainName=soporte.com&ipAddr1=192&ipAddr2=168&ipAddr3=1&ipAddr4=1&netMask=0&wan_dmz=0&WAN1ConnectionType=1&Wan1DnsNeq=1&mtu_auto1=1&WAN2ConnectionType=2&DmzSubnetRange=0&Wan2AliasIp1=0&Wan2AliasIp2=0&Wan2AliasIp3=0&Wan2AliasIp4=0&Wan2AliasMaskIp1=0&Wan2AliasMaskIp2=0&Wan2AliasMaskIp3=0&Wan2AliasMaskIp4=0
```

Observaciones:

- `DhcpEnabled1=+checked`: el valor literal es `" checked"`, con un espacio delante.
- `PPTPEnabled=+`: el valor es un espacio.
- No se envían `setWan1DNS`, `Wan1DnsA*` ni `Wan1DnsB*` porque están deshabilitados, ni `bytesMTU1`, ni `MLanSetting`.

**N2: hostname, dominio, DNS manual 8.8.8.8 / 1.1.1.1 y MTU manual 1492.** Solo cambian estos campos respecto de N1, y aparecen en la misma posición:

```
...&hostname=RV082&DomainName=casa.lan&...&WAN1ConnectionType=1&Wan1DnsNeq=0&setWan1DNS=1&Wan1DnsA1=8&Wan1DnsA2=8&Wan1DnsA3=8&Wan1DnsA4=8&Wan1DnsB1=1&Wan1DnsB2=1&Wan1DnsB3=1&Wan1DnsB4=1&mtu_auto1=0&bytesMTU1=1492&WAN2ConnectionType=2&...
```

**Qué modificar para cada ajuste:**

| Ajuste | Campos |
|---|---|
| Host name | `hostname` (≤31) |
| Dominio | `DomainName` (≤63) |
| IP LAN | `ipAddr1..4`. **No** tocar `LanIp*`, que llevan la IP *vieja* (ver N4) |
| Máscara LAN | `netMask` (0/128/…/252). **No** tocar `netMaskAll` ni `netMaskIp*` |
| DNS manual WAN1 (modo DHCP) | `Wan1DnsNeq=0`, añadir `setWan1DNS=1` y los 8 `Wan1DnsA1..4`/`B1..4` justo después de `Wan1DnsNeq` |
| Volver a DNS automático | `Wan1DnsNeq=1` y quitar `setWan1DNS` y `Wan1Dns*` |
| MTU manual | `mtu_auto1=0` y añadir `bytesMTU1=<68..1500>` justo después |
| MTU automático | `mtu_auto1=1` y sin `bytesMTU1` |

**N4: cambiar IP LAN a 192.168.1.2.** Hay un `confirm` que se acepta. El POST es igual a N1 salvo `ipAddr4=2`. **`LanIp=192.168.1.1` y `LanIp1..4=192,168,1,1` siguen con la IP vieja**: el servidor compara las dos.

### 1.4 WAN estática y PPPoE (campos ocultos hoy)

Para cambiar de tipo, lo fiel al navegador son dos pasos:

**Paso A: cambiar el combo.** Es el POST de `falseSubmit`, capturado en N3. Es igual que N1 pero con `submitStatus=0` y `WAN1ConnectionType=<nuevo>`:

```
page=network.htm&submitStatus=0&clickDualwan=0&clickDmz=0&...(igual que N1)...&WAN1ConnectionType=2&Wan1DnsNeq=1&mtu_auto1=1&WAN2ConnectionType=2&DmzSubnetRange=0&Wan2AliasIp1=0&...&Wan2AliasMaskIp4=0
```

**Paso B:** tomar el HTML de la respuesta (ya con el bloque nuevo descomentado), aplicar las mismas correcciones del onLoad, rellenar los campos y hacer POST con `submitStatus=1`.

(Mandar directamente `submitStatus=1` con `WAN1ConnectionType=2` y los campos estáticos probablemente funcione, pero no es lo que hace el navegador.)

**WAN1 Static IP (value 2).** El bloque está comentado hoy (líneas 1523-1619 del crudo). Campos, en orden:

- `Wan1AliasIp1..4`: IP WAN.
- `Wan1AliasMaskIp1..4`: máscara.
- `Wan1RouterIp1..4`: gateway.
- `Wan1DnsA1..4` y `Wan1DnsB1..4`: DNS 1 y 2.

En modo Static **no existen** `setWan1DNS` ni `Wan1DnsNeq`, porque están en el bloque DHCP, que queda comentado.

POST **SIMULADO** (N5: IP 200.1.2.10/24, gateway 200.1.2.1, DNS 8.8.8.8):

```
page=network.htm&submitStatus=1&clickDualwan=0&clickDmz=0&LanIp=192.168.1.1&LanIp1=192&LanIp2=168&LanIp3=1&LanIp4=1&dsPPTP1=192&dsPPTP2=168&dsPPTP3=1&dsPPTP4=200&dePPTP4=204&dsDHCP1=192&dsDHCP2=168&dsDHCP3=1&dsDHCP4=100&deDHCP4=149&netMaskAll=255.255.255.0&netMaskIp1=255&netMaskIp2=255&netMaskIp3=255&netMaskIp4=0&DhcpEnabled1=+checked&PPTPEnabled=+&hostname=TP-VPN&DomainName=soporte.com&ipAddr1=192&ipAddr2=168&ipAddr3=1&ipAddr4=1&netMask=0&wan_dmz=0&WAN1ConnectionType=2&Wan1AliasIp1=200&Wan1AliasIp2=1&Wan1AliasIp3=2&Wan1AliasIp4=10&Wan1AliasMaskIp1=255&Wan1AliasMaskIp2=255&Wan1AliasMaskIp3=255&Wan1AliasMaskIp4=0&Wan1RouterIp1=200&Wan1RouterIp2=1&Wan1RouterIp3=2&Wan1RouterIp4=1&Wan1DnsA1=8&Wan1DnsA2=8&Wan1DnsA3=8&Wan1DnsA4=8&Wan1DnsB1=0&Wan1DnsB2=0&Wan1DnsB3=0&Wan1DnsB4=0&mtu_auto1=1&WAN2ConnectionType=2&DmzSubnetRange=0&Wan2AliasIp1=0&Wan2AliasIp2=0&Wan2AliasIp3=0&Wan2AliasIp4=0&Wan2AliasMaskIp1=0&Wan2AliasMaskIp2=0&Wan2AliasMaskIp3=0&Wan2AliasMaskIp4=0
```

Validaciones JS por octeto (al salir del campo):

| Campos | Rango |
|---|---|
| `IPCheck`: octetos 1-3 | 0-255 |
| `IP0to254Check`: octeto 4 | 0-254 |
| `IP1to254Check`: `ipAddr4` | 1-254 |
| Máscara | 0-255 |

**WAN1 PPPoE (value 3).** El bloque está comentado hoy (líneas 1643-1744). Campos, en orden:

| Campo | Contenido | Límites |
|---|---|---|
| `Wan1UserName` | usuario | ≤60 |
| `Wan1PassWord` | clave (type=password) | ≤60 |
| `Wan1ServiceName` | nombre de servicio | ≤60, puede ir vacío |
| `Wan1ConnectAlive` | `1`=Connect on Demand, `2`=Keep Alive | |
| `Wan1IdleTime` | minutos | 1-99999 |
| `wan1_echo_interval` | segundos | 5-9999 |
| `wan1_echo_failure` | reintentos | 1-99 |
| `Wan1RedialTime` | segundos | 1-9999999 |

El orden real del documento es `Wan1UserName, Wan1PassWord, Wan1ServiceName, Wan1IdleTime, Wan1ConnectAlive, wan1_echo_interval, wan1_echo_failure, Wan1RedialTime`. Va `IdleTime` antes del radio marcado, cuando el radio marcado es el 2. En general, cada radio ocupa el lugar del input *marcado*.

POST **SIMULADO** (N6: usuario `usuario@isp`, clave `clave123`, Keep Alive). Desde `WAN1ConnectionType` en adelante:

```
...&wan_dmz=0&WAN1ConnectionType=3&Wan1UserName=usuario%40isp&Wan1PassWord=clave123&Wan1ServiceName=&Wan1IdleTime=5&Wan1ConnectAlive=2&wan1_echo_interval=30&wan1_echo_failure=5&Wan1RedialTime=30&mtu_auto1=1&WAN2ConnectionType=2&DmzSubnetRange=0&Wan2AliasIp1=0&...&Wan2AliasMaskIp4=0
```

**PPTP (value 4).** Comentado (líneas 1745-1842). Lleva `Wan1AliasIp1..4`, `Wan1AliasMaskIp1..4`, `Wan1RouterIp1..4`, `Wan1UserName`, `Wan1PassWord`, `Wan1ConnectAlive` (1/2), `Wan1IdleTime` y `Wan1RedialTime`. No tiene `ServiceName` ni echo.

**Otros tipos:**

- Heart Beat (8): `Wan1HBSUserName`, `Wan1HBSPassWord`, `Wan1HBSServer`.
- Bridge (7): campos estáticos más el hidden `wan1Bridge` y `Wan1LanIp1..5` (rango de LAN interna).

En modo Dual WAN, WAN2 tiene los mismos campos con prefijo `Wan2` y `mtu_auto2`/`bytesMTU2`.

### 1.5 Riesgos de `network.htm`

- **`ipAddr1..4` y `netMask` (IP y máscara LAN):** cambiarlos corta la sesión. El router pasa a la IP nueva, la PC (fija en 192.168.1.250) puede quedar fuera de la subred, y además cambia el rango DHCP.
- **No reenviar `LanIp1..4` ni `netMaskIp1..4` del HTML crudo.** Vienen como `196,'','',''` y `'','','',''`; hay que recalcularlos desde `LanIp` y `netMaskAll`.
- **`Wan1DnsNeq`:** en el crudo es `0`, pero el navegador manda `1` cuando el checkbox está sin marcar. Si se manda `0` sin los `Wan1Dns*`, podría activar "DNS manual" con 0.0.0.0 y dejar la WAN sin resolución.
- **`wan_dmz`, `clickDualwan` y `clickDmz`:** no tocar. Pasar a Dual WAN o DMZ reconfigura el puerto DMZ/WAN2. Siempre enviar `clickDualwan=0` y `clickDmz=0`.
- **`WAN1ConnectionType`:** un tipo mal configurado deja al router sin Internet. Con un servidor remoto, eso es perder el acceso.
- **`Wan2AliasIp*` y `Wan2AliasMask*` (subred DMZ):** reenviarlos tal cual.
- **Hidden informativos** (`dsDHCP*`, `deDHCP4`, `dsPPTP*`, `dePPTP4`, `DhcpEnabled1`, `PPTPEnabled`): reenviarlos exactamente igual, con los espacios incluidos.
- **Clave PPPoE:** hoy `Wan1PassWord` viene con `value=''` porque no hay nada configurado. **No se sabe si el servidor rellena la clave guardada en el HTML.** Si la deja vacía, un "guardar sin cambios" en modo PPPoE podría borrar la clave. Hay que verificarlo la primera vez que se configure PPPoE.

---

## 2. `dhcp_setup.htm` (servidor DHCP, rango, lease, DNS/WINS, reservas IP-MAC, DNS Local Database)

### 2.1 Cómo leer los valores actuales

El form es **`formDHCPSetup`** (`action="dhcp_setup.htm" method="post"`).

| Dato | Campo | Hoy |
|---|---|---|
| DHCP activado | checkbox `dhcpStatus` con **`value="0"`** y `checked`. JS `chDismatch`: está activado si existe `clTime` | sí |
| Relay DHCP | checkbox `dhcpRelay` (`value="0"`) | no |
| Servidor del relay | `dhcpserverAddr1..4`, en bloque comentado salvo con relay activo | — |
| Lease (min) | `clTime` (5-43200) | 1440 |
| Rango inicio | hidden `ds1,ds2,ds3` (fijos = red LAN) y texto `ds4` | .100 |
| Rango fin | hidden `de1,de2,de3` y texto `de4` | .149 |
| DNS que reparte | `LanDnsA1..4`, `LanDnsB1..4` (0.0.0.0 = usa el router) | 0.0.0.0 |
| WINS | `WSip1..4` | 0.0.0.0 |
| Bloqueos | checkbox `BlockMacWrongIP` (value 1) y `BlockMacNotList` (value 1) | ambos sin marcar |
| Reservas IP-MAC | `<select multiple name="dhcp_staticList1">` | vacía |
| DNS Local Database | `<select multiple name="dhcp_dnsList">` | vacía |
| Informativos | hidden `LanIp`, `LanMask`, `deviceIP`, `dsPPTP4`, `dePPTP4`, `PPTPEnabled` | |

**Formato de las listas.** Se dedujo del JS que las arma (`IpMACaddSel`, `dnsaddSel`) y del que las desarma (`showdeleteButton2`, `showdeleteDns2`). Hoy están vacías, así que no se vio una opción generada por el servidor; el parser tiene que ser tolerante.

Reserva IP-MAC: lo que importa es el `value` de cada `<option>`, que es lo que se envía.

```
value = "<IP> => <MAC> <enable> <nombre>"
        ej. "192.168.1.50 => aa-bb-cc-dd-ee-0f 1 pc1"
text  = "<IP> => <MAC>=><nombre>=><Enabled|Disabled>"
```

- MAC: 6 pares hex separados por `-`. `MACCheck` antepone `0` si un par tiene 1 carácter.
- `enable`: `1` o `0` (el checkbox `dhcpEnable` del formulario de alta).
- Nombre (`userName`): ≤12 caracteres. Al desarmar, el nombre es todo lo que sigue al 2º espacio después de la MAC. Mejor sin espacios.
- Máximo 253 entradas.
- La IP `0.0.0.0` está permitida, porque se saltea el control de IP duplicada.
- No se permite la IP del router (`deviceIP`), ni IP o MAC duplicadas.
- Tras cada alta, `sortIP` ordena la lista por IP ascendente.

DNS local: el `value` de cada `<option>` tiene esta forma.

```
value = "<IP> => <hostname>"
        ej. "192.168.1.40 => nas.casa"
text  = "<hostname> => <IP>"
```

- `hostname`: ≤32 caracteres y no puede repetirse.
- El JS deja llegar a 101 entradas (el mensaje dice 100).

### 2.2 Qué hace "Save Settings" (`javascript: chSubmit(document.formDHCPSetup)`)

1. `selAll(dhcp_dnsList)`: **invierte el orden de la lista** (`exPosion`) y selecciona todas las opciones.
2. **`dhcpStatusChange`** = `1` si `dhcpStatus` está marcado, si no `0`. **`dhcpRelayChange`** = `1` o `0` según `dhcpRelay`. En el crudo, `dhcpStatusChange` vale `0`. **Mandarlo así con DHCP activo puede apagar el DHCP.**
3. Si existen los campos del relay, exige que la IP del servidor relay no sea vacía ni 0.0.0.0.
4. Si `ds4 > de4`, los intercambia. Si PPTP está activo y el rango se pisa con el de PPTP (.200-.204), da error.
5. **Si DHCP está desmarcado**: `submitStatus=1`, `selAll(dhcp_staticList1)` y submit inmediato.
6. Si está marcado:
   - `selAll(dhcp_staticList1)`: también **invierte** la lista y la selecciona entera.
   - Si DNS1 = 0.0.0.0 y DNS2 ≠ 0, intercambia.
   - Vuelve a revisar el orden de ds4/de4.
   - `submitStatus=1` y **POST a `/dhcp_setup.htm`**.

Checkbox `dhcpStatus` y `dhcpRelay`: al hacer clic se llama a `falseSubmit(F,1|2)`. Esta función ajusta `dhcpStatusChange`/`dhcpRelayChange`, pone `submitStatus=0`, selecciona la lista estática y hace submit. El servidor vuelve a dibujar la página (por ejemplo sin el bloque de rango) y después el usuario pulsa Save.

Los botones "Add to list", "Delete selected Entry" y "Update this Entry" **solo tocan el `<select>` en el navegador**. Nada se guarda hasta pulsar "Save Settings", que envía **la lista completa**.

### 2.3 POST exacto (capturado)

**D1: Save sin cambios, estado actual** (DHCP on, .100-.149, 1440 min, listas vacías):

```
POST /dhcp_setup.htm
page=dhcp_setup.htm&submitStatus=1&dhcpStatusChange=1&dhcpRelayChange=0&LanIp=192.168.1.1&LanMask=255.255.255.0&dsPPTP4=200&dePPTP4=204&PPTPEnabled=+&deviceIP=192.168.1.1&dhcpStatus=0&clTime=1440&ds1=192&ds2=168&ds3=1&ds4=100&de1=192&de2=168&de3=1&de4=149&ss1=&ss2=&ss3=&ss4=&sMAC1=&sMAC2=&sMAC3=&sMAC4=&sMAC5=&sMAC6=&userName=&LanDnsA1=0&LanDnsA2=0&LanDnsA3=0&LanDnsA4=0&LanDnsB1=0&LanDnsB2=0&LanDnsB3=0&LanDnsB4=0&WSip1=0&WSip2=0&WSip3=0&WSip4=0&hostname=&dns_ss1=&dns_ss2=&dns_ss3=&dns_ss4=
```

Observaciones:

- **`dhcpStatus=0` significa "DHCP activado"**, porque el value del checkbox es "0". El flag real es `dhcpStatusChange=1`.
- Los campos de alta (`ss1..4`, `sMAC1..6`, `userName`, `hostname`, `dns_ss1..4`) viajan **vacíos**.
- `dhcpEnable` (checkbox del alta) no viaja, porque queda desmarcado tras cada alta.
- `hostname` aquí es el campo de alta del DNS local, no el hostname del router.

**D2: lease 720, rango .100-.199, DNS LAN 192.168.1.1/8.8.8.8, 2 reservas y 1 DNS local:**

```
page=dhcp_setup.htm&submitStatus=1&dhcpStatusChange=1&dhcpRelayChange=0&LanIp=192.168.1.1&LanMask=255.255.255.0&dsPPTP4=200&dePPTP4=204&PPTPEnabled=+&deviceIP=192.168.1.1&dhcpStatus=0&clTime=720&ds1=192&ds2=168&ds3=1&ds4=100&de1=192&de2=168&de3=1&de4=199&ss1=&ss2=&ss3=&ss4=&sMAC1=&sMAC2=&sMAC3=&sMAC4=&sMAC5=&sMAC6=&userName=&dhcp_staticList1=192.168.1.50+%3D%3E+aa-bb-cc-dd-ee-0f+1+pc1&dhcp_staticList1=192.168.1.40+%3D%3E+11-22-33-44-55-66+0+tele&LanDnsA1=192&LanDnsA2=168&LanDnsA3=1&LanDnsA4=1&LanDnsB1=8&LanDnsB2=8&LanDnsB3=8&LanDnsB4=8&WSip1=0&WSip2=0&WSip3=0&WSip4=0&hostname=&dns_ss1=&dns_ss2=&dns_ss3=&dns_ss4=&dhcp_dnsList=192.168.1.40+%3D%3E+nas.casa
```

**Cómo se codifican las listas en el POST:** un par `dhcp_staticList1=<value>` por cada reserva, en el lugar del `<select>`, entre `userName` y `BlockMacWrongIP`/`LanDnsA1`. Lo mismo con `dhcp_dnsList=<value>` al final. No hay hidden con separadores: es el `<select multiple>` con todas las opciones seleccionadas.

**Orden:** el navegador envía la lista **al revés de como se muestra**, por `exPosion`:

- En D2, el JS la ordenó ascendente (.40, .50) y se envió .50, .40.
- En D4 (SIMULADO, lista mostrada .20, .30) se envió:

```
...&userName=&dhcp_staticList1=192.168.1.30+%3D%3E+00-11-22-33-44-02+0+nas&dhcp_staticList1=192.168.1.20+%3D%3E+00-11-22-33-44-01+1+impresora&LanDnsA1=0&...&dns_ss4=&dhcp_dnsList=192.168.1.30+%3D%3E+nas.lan&dhcp_dnsList=192.168.1.20+%3D%3E+impresora.lan
```

Probablemente el orden no le importe al servidor, pero para imitarlo: lista leída del HTML, invertida.

**Altas, bajas y cambios en las listas:**

| Operación | Qué enviar |
|---|---|
| Añadir reserva | La lista actual completa más la nueva. Para imitar al navegador exactamente: ordenar por IP ascendente y después invertir |
| Borrar reserva | Reenviar la lista **sin** esa entrada (D5: queda solo `dhcp_staticList1=192.168.1.20+%3D%3E+00-11-22-33-44-01+1+impresora`) |
| Editar reserva | Reemplazar su `value` |
| Borrar todas | No enviar ningún `dhcp_staticList1` |
| DNS local | Igual, con `dhcp_dnsList` |

**Qué modificar para cada ajuste:**

| Ajuste | Campos |
|---|---|
| Lease | `clTime` (5-43200) |
| Rango | `ds4` y `de4`, dentro de la red LAN: 1-254 para /24 (`NetworkRangeCheck`). **No** tocar `ds1-3` ni `de1-3` |
| DNS repartidos | `LanDnsA1..4`, `LanDnsB1..4` |
| WINS | `WSip1..4` |
| Bloquear MAC con IP incorrecta | añadir `BlockMacWrongIP=1` después de la última `dhcp_staticList1`, o de `userName` si no hay ninguna |
| Bloquear MAC fuera de la lista | añadir `BlockMacNotList=1` (D6) |

**Desactivar el servidor DHCP** (como el navegador):

1. **Paso A**: el POST de `falseSubmit`, capturado en D3. Es D1 con `submitStatus=0&dhcpStatusChange=0` y **sin `dhcpStatus`**:

   ```
   page=dhcp_setup.htm&submitStatus=0&dhcpStatusChange=0&dhcpRelayChange=0&LanIp=192.168.1.1&LanMask=255.255.255.0&dsPPTP4=200&dePPTP4=204&PPTPEnabled=+&deviceIP=192.168.1.1&clTime=1440&ds1=192&...(igual que D1)...&dns_ss4=
   ```

2. **Paso B**: tomar la página de la respuesta y hacer Save con `dhcpStatus` sin marcar. Eso da `submitStatus=1&dhcpStatusChange=0`, sin `dhcpStatus` y con la lista estática entera.

Reactivar DHCP es lo inverso, con `dhcpStatusChange=1` y `dhcpStatus=0`.

### 2.4 Riesgos de `dhcp_setup.htm`

- **Mandar siempre las listas completas.** Un POST sin `dhcp_staticList1` o sin `dhcp_dnsList` **borra todas las reservas o todo el DNS local**.
- **`dhcpStatusChange` es lo que manda, no `dhcpStatus`.** Si se reenvía el `0` del HTML crudo con DHCP activo, puede apagarse el DHCP de la LAN.
- **`BlockMacNotList=1`** bloquea todo equipo que no esté en la lista de reservas. La PC de gestión (192.168.1.250, IP fija, fuera de la lista) podría perder el acceso. **No activarlo** sin antes reservar las MAC necesarias.
- **`BlockMacWrongIP=1`:** un equipo de la lista con otra IP queda bloqueado.
- **`ds1-3`, `de1-3`, `LanIp`, `LanMask` y `deviceIP`:** reenviarlos tal cual; los fija la LAN. Si la IP o la máscara LAN cambiaron en `network.htm`, volver a leer `dhcp_setup.htm` antes de guardar aquí.
- **Relay DHCP (`dhcpRelay`):** desactiva el servidor DHCP propio.
- **`hostname` de esta página** es el campo de alta del DNS local. Dejarlo vacío, como el navegador.

---

## 3. `dhcp_status.htm` (clientes DHCP)

### 3.1 Lectura

El form es `formdhcp_status` (`action="dhcp_status.htm"`), con hidden `page=dhcp_status.htm` y `RemoveLine=0`.

El resumen es texto en una tabla de 2 columnas. La etiqueta va en `<b>` dentro de un `<div align=right>`, y el valor en el `<td>` siguiente, precedido de `&nbsp;`:

| Etiqueta | Hoy |
|---|---|
| `DHCP Server :` | 192.168.1.1 |
| `Dynamic IP Used :` | 0 |
| `Static IP Used :` | 0 |
| `DHCP Available :` | 50 |
| `Total :` | 50 |

Para extraer: quitar los tags, colapsar espacios y aplicar `r"Dynamic IP Used :\s*(\d+)"`, etc.

La tabla de clientes es una tabla `border=1` con la cabecera `Client Host Name | IP Address | MAC Address | Leased Time | Delete`. **Hoy está vacía**: no hay clientes, porque la PC usa IP fija. Por eso no se pudo ver el HTML real de una fila. Lo esperable son filas `<tr>` con 5 `<td>`: nombre, IP, MAC, tiempo de lease y un enlace `javascript:removeLine(N)`.

Parser recomendado: tomar todos los `<tr>` de esa tabla después de la cabecera y leer el texto de los 4 primeros `<td>`. Extraer `N` con `removeLine\((\d+)\)`.

### 3.2 Escritura (solo "Delete")

`removeLine(n)` pide confirmación, pone `RemoveLine=n` y hace POST de `page=dhcp_status.htm&RemoveLine=<n>`.

No hay Save. "Refresh" es un GET. **No se sabe** si `N` empieza en 0 o en 1. El hidden por defecto `0` sugiere que 0 significa "nada" y que N empieza en 1, pero hay que confirmarlo leyendo el `href` real de una fila. Borrar un cliente solo libera el lease, no toca la configuración.

---

## 4. `lan_status.htm` (estado de puertos)

### 4.1 Lectura

El form es `formlan_status` (`action="lan_status.htm"`): hidden `page=lan_status.htm`, `dualwanEnabled=0` y `<select name="port">`. Los valores van de 1 a 8 (puertos LAN), `9` es DMZ/Internet (WAN2) y `10` es Internet (WAN1).

**Un GET muestra siempre el puerto 1.** Para ver otro puerto, el navegador hace `turnPort()`, que es un POST `page=lan_status.htm&dualwanEnabled=0&port=<n>`. No cambia la configuración, pero es un POST.

**Alternativa solo con GET (recomendada):** `GET /port<N>_information.htm` con N de 1 a 8, `GET /dmz_port_information.htm` y `GET /wan_port_information.htm`. Son los popups de `openPort()` en `nk.js` y traen los mismos datos. Verificado con `port8_information.htm`:

```
Type 10Base-T / 100Base-TX | Interface LAN | Link Status Up | Port Activity Port Enabled | Priority Normal |
Speed Status 100 Mbps | Duplex Status Full | Auto negotiation Enabled | VLAN VLAN1 |
Port Receive Packet Count 8680 | Port Receive Packet Byte Count 822441 |
Port Transmit Packet Count 10733 | Port Transmit Packet Byte Count 6814544 | Port Packet Error Count 0
```

Formato: cada fila es `<td>Etiqueta</td><td>&nbsp; valor</td>`. Para extraer: quitar los comentarios HTML (hay filas comentadas, como "Receive Packet Error Count"), quitar los `<script>`, quitar los tags y buscar con regex las etiquetas:

- `Link Status`, `Port Activity`, `Speed Status`, `Duplex Status`, `Auto negotiation`, `Interface`.
- Contadores `Port (Receive|Transmit) Packet (Byte )?Count` y `Port Packet Error Count`.

En `lan_status.htm`, "Priority" y "VLAN" los escribe JS con `document.write`: `Normal`/`VLAN1` para los puertos LAN y `--` para WAN/DMZ.

**Estado rápido de todos los puertos de una vez:** en `home.htm`, mirar las imágenes (ver 5.1).

### 4.2 Escritura

No hay nada que guardar en esta página. La configuración de puertos (velocidad, prioridad, VLAN) está en `lan_setting.htm`, que no forma parte de este análisis.

---

## 5. `home.htm` (System Summary)

### 5.1 Lectura

Para extraer el texto: quitar los `<!-- -->` y los `<script>…</script>`, quitar los tags, reemplazar `&nbsp;` y colapsar espacios. Valores de hoy:

| Dato | Regex sobre el texto limpio | Hoy |
|---|---|---|
| Serie | `Serial Number :\s*(\S+)` | XXXXXXXXXXX |
| Firmware | `Firmware version :\s*(.+?)\s*\(` y la fecha de compilación entre paréntesis | 2.0.0.19-tm (Feb 20 2009 15:15:20) |
| CPU / DRAM / Flash | `CPU :\s*(\S+ \S+)`, `DRAM :\s*(\S+)`, `Flash :\s*(\S+)` | Intel IXP425-533, 32M, 16M |
| Uptime | `System up time :\s*(.+?)\s*\(Now:\s*(.+?)\s*\)` | `0 Days 0 Hours 23 Minutes 48 Seconds`, ahora `Thu Nov 12 2026 03:26:22` |
| IP LAN | `LAN IP :\s*([\d.]+)` | 192.168.1.1 |
| IP WAN (WAN1) | la primera IP después de "LAN IP …" (el texto "WAN IP" lo escribe JS) | 0.0.0.0 (WAN sin conexión) |
| IP DMZ/WAN2 | **dentro de un script**: `document.write('0.0.0.0 &nbsp;…')`. Buscar en el HTML crudo `document.write\('([\d.]+)` en el bloque de DMZ IP. Si `dualwanEnabled=0` y `DmzRangeFlag=1`, muestra `---` | 0.0.0.0 |
| Modo | `Mode :\s*(\w+)` | Gateway |
| DNS | celda `<td colspan="2">` después del enlace DNS. Hoy está vacía; con WAN conectada traerá las IP | (vacío) |
| DDNS | `DDNS\s*:\s*(\w+)` | Off |
| DMZ Host | `DMZ Host :\s*(\w+)` | Disabled |
| VPN | `Tunnel\(s\) Used :\s*(\d+)`, `Tunnel\(s\) Available :\s*(\d+)` | 0 / 100 |
| Firewall SPI / DoS / Block WAN | los tres salen del **mismo** hidden `firewall0` en `formdualwan`: `' checked'` es On, `''` es Off | On |
| Dual WAN | hidden `dualwanEnabled` (en `formdualwan` y `formsummary`): 0 es modo DMZ | 0 |

Estado de puertos (enlace up/down) por nombre de imagen en el HTML crudo: `images_rv082/<id>_<0|1>.gif`, donde **1 = enlace activo**.

- `po1`..`po8`: puertos LAN 1-8.
- `wan`: WAN.
- `dmz`: DMZ/WAN2.
- `L1`..`L8`, `Lwan`, `Ldmz`, `Ldmzmode`: LEDs y etiquetas.

Regex: `images_rv082/(po\d|wan|dmz)_(\d)\.gif`. Hoy solo `po8_1` está activo, que es el cable de la PC.

### 5.2 Escritura: NO usar

El form `formsummary` (`action="home.htm#1"`) **no tiene "Save Settings"**. Sus POST hacen acciones:

- `falseSubmit('10')`: botón **Release**, `submitStatus=10`, suelta la IP WAN.
- `falseSubmit('11')`: botón **Renew**, `submitStatus=11`.
- `getspstatus=11/111`: activación de Trend Micro ProtectLink.

Nunca hacer POST a `home.htm`. Con Release, el router se queda sin WAN. `UDI` cambia en cada carga y no importa.

---

## 6. Implementación de referencia en Python (validada contra el navegador)

Este código produce **exactamente** el mismo cuerpo, mismos pares y mismo orden, que el navegador. Lo comprobé en 5 casos: N1 (network DHCP), N5 (static SIMULADO), N6 (PPPoE SIMULADO), D1 (dhcp vacío) y D4 (dhcp con listas SIMULADO).

```python
import re
from html.parser import HTMLParser
from urllib.parse import urlencode

class _FormParser(HTMLParser):
    def __init__(self, form_name):
        super().__init__(convert_charrefs=True)
        self.form_name, self.inside, self.ctrls = form_name, False, []
        self._sel = None; self._opt = None
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "form":
            self.inside = (a.get("name") == self.form_name); return
        if not self.inside: return
        if tag == "input":
            self.ctrls.append({"tag": "input", "type": a.get("type", "text").lower(), "name": a.get("name"),
                               "value": a.get("value", ""), "checked": "checked" in a,
                               "disabled": "disabled" in a})
        elif tag == "select":
            self._sel = {"tag": "select", "name": a.get("name"), "multiple": "multiple" in a,
                         "disabled": "disabled" in a, "options": []}
            self.ctrls.append(self._sel)
        elif tag == "option" and self._sel is not None:
            self._opt = {"value": a.get("value"), "selected": "selected" in a, "text": ""}
            self._sel["options"].append(self._opt)
    def handle_data(self, d):
        if self._opt is not None: self._opt["text"] += d
    def handle_endtag(self, tag):
        if tag == "form": self.inside = False
        if tag == "select": self._sel = None
        if tag == "option": self._opt = None

def parse_form(html, form_name):
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)   # quitar bloques comentados
    p = _FormParser(form_name); p.feed(html)
    for c in p.ctrls:
        if c["tag"] == "select":
            for o in c["options"]:
                if o["value"] is None: o["value"] = o["text"].strip()
    return p.ctrls

def ctrl(ctrls, name):
    return [c for c in ctrls if c.get("name") == name]

def serialize(ctrls, multi_select_all=False):
    out = []
    for c in ctrls:
        if not c.get("name") or c.get("disabled"): continue
        if c["tag"] == "input":
            t = c["type"]
            if t in ("button", "submit", "reset", "image", "file"): continue
            if t in ("checkbox", "radio"):
                if c["checked"]: out.append((c["name"], c["value"] or "on"))
                continue
            out.append((c["name"], c["value"]))
        else:
            opts = c["options"]
            if c["multiple"]:
                for o in (opts if multi_select_all else [o for o in opts if o["selected"]]):
                    out.append((c["name"], o["value"]))
            elif opts:
                sel = [o for o in opts if o["selected"]] or [opts[0]]
                out.append((c["name"], sel[-1]["value"]))
    return out

def network_fixups(ctrls):            # = onLoad + chSubmit de network.htm
    v = lambda n: ctrl(ctrls, n)[0]["value"]
    lan = v("LanIp").strip().split(" ")[0].split(".")
    for i in range(4): ctrl(ctrls, f"LanIp{i+1}")[0]["value"] = lan[i]
    msk = v("netMaskAll").strip().split(" ")[0].split(".")
    for i in range(4): ctrl(ctrls, f"netMaskIp{i+1}")[0]["value"] = msk[i]
    wt = ctrl(ctrls, "WAN1ConnectionType")[0]
    wt_sel = ([o for o in wt["options"] if o["selected"]] or [wt["options"][0]])[-1]["value"]
    if wt_sel == "1" and ctrl(ctrls, "setWan1DNS"):
        on = ctrl(ctrls, "setWan1DNS")[0]["checked"]
        ctrl(ctrls, "Wan1DnsNeq")[0]["value"] = "0" if on else "1"
        for n in ("A", "B"):
            for i in range(1, 5):
                for c in ctrl(ctrls, f"Wan1Dns{n}{i}"): c["disabled"] = not on
    for k in ("1", "2"):
        r = ctrl(ctrls, f"mtu_auto{k}")
        if r and ctrl(ctrls, f"bytesMTU{k}"):
            ctrl(ctrls, f"bytesMTU{k}")[0]["disabled"] = any(c["checked"] and c["value"] == "1" for c in r)
    for n in ("WAN1ConnectionType", "WAN2ConnectionType"):
        for c in ctrl(ctrls, n): c["disabled"] = False
    return ctrls
    # (en modo Dual WAN con WAN2=DHCP habría que replicar también setWan2DNS/Wan2DnsNeq)

def dhcp_fixups(ctrls):               # = chSubmit de dhcp_setup.htm
    ctrl(ctrls, "dhcpStatusChange")[0]["value"] = "1" if ctrl(ctrls, "dhcpStatus")[0]["checked"] else "0"
    ctrl(ctrls, "dhcpRelayChange")[0]["value"] = "1" if ctrl(ctrls, "dhcpRelay")[0]["checked"] else "0"
    ctrl(ctrls, "submitStatus")[0]["value"] = "1"
    for n in ("dhcp_staticList1", "dhcp_dnsList"):
        for c in ctrl(ctrls, n): c["options"].reverse()      # selAll() invierte
    return ctrls

# Uso típico (cambiar hostname):
#   html = GET /network.htm  (decodificar latin-1)
#   cs = network_fixups(parse_form(html, "formNetwork"))
#   ctrl(cs, "hostname")[0]["value"] = "RV082"
#   body = urlencode(serialize(cs, multi_select_all=True))
#   POST /network.htm  body, Content-Type: application/x-www-form-urlencoded
# Para checkbox/radio: cambiar "checked" en el control (y para radios desmarcar los demás
# del mismo name). Para habilitar un campo deshabilitado por JS: "disabled"=False.
# Para listas DHCP: editar ctrl(cs,"dhcp_staticList1")[0]["options"] (lista de dicts con
# "value") ANTES de dhcp_fixups, o invertir a mano después.
```

**Verificación después de cada guardado:** volver a hacer `GET` de la página y comparar los valores leídos con los esperados. Todavía no se observó qué devuelve el POST (si es la página otra vez o un mensaje de "Settings are successful").

---

## 7. Comportamientos raros y dudas abiertas

1. **`LanIp1='196'`** en el HTML crudo de `network.htm`. Es un valor basura que el onLoad corrige; quien parsee sin JS manda un dato erróneo.
2. **Los checkbox `dhcpStatus` y `dhcpRelay` tienen `value="0"`.** Marcado envía `dhcpStatus=0`. Lo que cuenta es `dhcpStatusChange`.
3. **El navegador invierte las listas DHCP** antes de enviarlas (`selAll` llama a `exPosion`). Si el servidor guarda en el orden recibido, el orden se invertiría en cada guardado. No tiene consecuencias funcionales conocidas.
4. **Campos con nombre duplicado dentro de comentarios** (`network.htm`): obligan a quitar los `<!-- -->` antes de parsear.
5. **`hostname` existe en dos páginas** con significados distintos: el host del router en `network.htm` y el alta del DNS local en `dhcp_setup.htm`.
6. **Pendiente de confirmar con el router en otro estado**, porque hoy no se puede ver:
   - el HTML real de WAN Static/PPPoE (lo simulé descomentando el bloque y comentando el de DHCP);
   - el formato exacto de las `<option>` de reservas y DNS local que dibuja el servidor;
   - las filas de clientes en `dhcp_status.htm` y la numeración de `RemoveLine`;
   - si la clave PPPoE se vuelve a mostrar en `value`;
   - qué responde el servidor a un POST de guardado.
7. **El popup "Show unknown MAC addresses"** (`Dhcp_table1.htm`, GET de solo lectura) también puede añadir reservas por su cuenta. Su form `dhcp_ip_mac_bind` hace POST con checkboxes `bindable*` y el hidden `dhcptotal`. Hoy está vacío y no se analizó a fondo.
8. **En `home.htm` los tres indicadores de firewall** salen del mismo hidden `firewall0`, así que no son independientes.
