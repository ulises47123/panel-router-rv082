# Muestra la barra de tareas (si está oculta) moviendo el mouse al borde inferior
# y captura la franja de abajo para ver el ícono de la bandeja.
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$antes = [System.Windows.Forms.Cursor]::Position
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$x = [int]$b.Width - 300
$y = [int]$b.Height - 1
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($x, $y)
Start-Sleep -Milliseconds 1800
$alto = 90
$bmp = New-Object System.Drawing.Bitmap ([int]$b.Width), $alto
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, ([int]$b.Height - $alto), 0, 0, (New-Object System.Drawing.Size ([int]$b.Width), $alto))
$bmp.Save($args[0])
[System.Windows.Forms.Cursor]::Position = $antes
"ok"
