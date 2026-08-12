# FellSplit Pro 1.3.0

FellSplit Pro setzt ein normales Windows-Spiel-Fenster rahmenlos auf einen frei
einstellbaren Bildschirmbereich, sperrt die Maus dort ein und kann ein zweites
Fenster wie OBS rahmenlos in der verbleibenden Zone halten. Seit Version 1.3
werden Monitor, Aufloesung und passende Zonen automatisch erkannt. Feste
5120-x-1440-Koordinaten sind nicht mehr erforderlich.

Unterstuetzte Layoutmodi:

| Modus | Verhalten auf 32:9 | Verhalten auf 21:9 |
| --- | --- | --- |
| Automatisch passend | Zwei gleich grosse 16:9-Zonen | 16:9-Spielzone plus Restflaeche |
| 50/50 | Zwei gleich grosse Zonen | Zwei gleich grosse, nicht 16:9-Zonen |
| Spiel 16:9 + Restflaeche | 16:9-Spielzone plus Rest | 16:9-Spielzone plus Rest |
| Benutzerdefiniert | Freie X/Y/Breite/Hoehe | Freie X/Y/Breite/Hoehe |

Beispiele fuer **Automatisch passend**:

- `5120 x 1440` -> Spiel `2560 x 1440`, zweite Zone `2560 x 1440`
- `3840 x 1080` -> Spiel `1920 x 1080`, zweite Zone `1920 x 1080`
- `3440 x 1440` -> Spiel `2560 x 1440`, zweite Zone `880 x 1440`
- `2560 x 1080` -> Spiel `1920 x 1080`, zweite Zone `640 x 1080`

Das Spiel kann links oder rechts liegen. Bei mehreren Displays ist der zu
verwendende Monitor auswaehlbar; auch negative Windows-Koordinaten werden
unterstuetzt.

## Installation (empfohlen)

Voraussetzung: 64-Bit Windows 10 oder Windows 11. Eine separate
Python-Installation ist fuer die fertige App nicht erforderlich.

1. Beende eine noch laufende SplitLock-/FellSplit-Pro-Instanz ueber das
   Tray-Menue **Beenden**. Der Installer schuetzt so Maus und Taskleiste vor
   einem harten Prozessabbruch.
2. Starte `FellSplit-Pro-Setup-1.3.0.exe`.
3. Folge dem deutschsprachigen Installationsassistenten. Auf der Seite
   **Ziel-Ordner waehlen** kannst du den vorgeschlagenen Pfad bearbeiten oder
   ueber **Durchsuchen** einen eigenen Installationsordner auswaehlen. Die
   Seite wird auch bei einem Update immer angezeigt.
4. Der Installer legt einen Startmenue-Eintrag und auf Wunsch eine
   Desktop-Verknuepfung an.
5. Oeffne **FellSplit Pro** wie jedes andere Windows-Programm. Es erscheint
   keine Eingabeaufforderung.
6. Stelle das Spiel auf den **normalen Fenstermodus**. Verwende im Spiel weder
   exklusives Vollbild noch "Randlos/Vollbild-Fenster". FellSplit Pro entfernt
   den sichtbaren Windows-Rahmen danach selbst. Nur so erhaelt das Spiel eine
   die von FellSplit Pro berechnete Clientflaeche statt weiterhin den gesamten
   Desktop zu verwenden.
7. Die automatische Erkennung ist standardmaessig aktiv. Starte das Spiel und
   bringe es fuer etwa 1,5 Sekunden in den Vordergrund. Alternativ kannst du
   weiterhin ein Fenster oder `Wow.exe` fest vorgeben.
8. Waehle unter **Monitor und Layout** den gewuenschten Monitor, den Modus
   **Automatisch passend** und die Spielseite. Die Vorschau zeigt beide Zonen.
9. Speichere und aktiviere den grossen Schalter auf der Startseite.

Beim ersten Start unter dem neuen Namen uebernimmt FellSplit Pro automatisch
vorhandene Einstellungen aus `%APPDATA%\SplitLock\config.json`. Die alte Datei
bleibt als Sicherung erhalten; neue Aenderungen landen unter
`%APPDATA%\FellSplit Pro\config.json`. Auch ein alter SplitLock-Autostart wird
auf den neuen Namen und Programmpfad umgestellt.

## Schnellstart direkt aus dem Quellordner

Voraussetzungen: Windows 10/11 und Python 3.10 oder neuer.

1. Entpacke den gesamten Ordner.
2. Starte `start_fellsplit_pro.bat` per Doppelklick. Beim ersten Start werden
   die GUI- und Tray-Komponenten automatisch installiert. Danach bleibt keine
   Eingabeaufforderung offen.
3. Stelle das Spiel auf den **normalen Fenstermodus**. Verwende im Spiel weder
   exklusives Vollbild noch "Randlos/Vollbild-Fenster".
4. Die automatische Erkennung ist standardmaessig aktiv. Starte das Spiel und
   bringe es fuer etwa 1,5 Sekunden in den Vordergrund. Alternativ kannst du
   weiterhin ein Fenster oder `Wow.exe` fest vorgeben.
5. Waehle unter **Monitor und Layout** den Monitor, das Layout und die
   Spielseite. Speichere anschliessend.
6. Aktiviere den grossen Schalter auf der Startseite.

Fuer OBS aktiviere unter **Einstellungen > Zweite Zone / OBS** den Dual-Zone-
Modus und waehle `obs64.exe` beziehungsweise das geoeffnete OBS-Fenster. OBS
wird automatisch in die vom Layout berechnete freie Zone gesetzt. Mit der
standardmaessig aktiven Option
**Fensterleiste bei OBS-Fokus zeigen** erscheint nach Alt+Tab auf OBS wieder die
Titelleiste inklusive Minimieren, Maximieren und X. Beim Wechsel zurueck ins
Spiel wird OBS wieder rahmenlos.

Der Standard-Hotkey **Strg+Alt+F10** schaltet FellSplit Pro global an oder aus. So
kannst du die Maus auch aus dem Spiel heraus jederzeit freigeben.

Die Option **Taskleiste beim Spielen verstecken** ist standardmaessig aktiv.
Solange das Spiel den Fokus hat, kann die automatisch ausgeblendete Taskleiste
dadurch nicht an der unteren Kante aufklappen. Bei Alt+Tab erscheint sie wieder.

## Manuelle Installation

Oeffne PowerShell oder die Eingabeaufforderung in diesem Ordner:

```powershell
py -m pip install -r requirements.txt
pyw FellSplitPro.pyw
```

Verwendet werden `customtkinter`, `pystray` und `Pillow`. `pywin32`, `keyboard`
und `psutil` sind nicht notwendig; Fenstersteuerung und Hotkey verwenden direkt
die Win32-API ueber Pythons `ctypes`.

## Was das Programm robust macht

- **Monitor- und Aufloesungserkennung:** Alle aktiven Windows-Monitore werden
  mit ihrer echten physischen Aufloesung und Position aufgelistet. Der
  Hauptmonitor kann dynamisch verfolgt oder ein bestimmtes Display ausgewaehlt
  werden.
- **Flexible Layoutprofile:** Automatik, 50/50, 16:9 plus Restflaeche und freie
  Pixelwerte decken 32:9, 21:9 sowie eigene Sonderlayouts ab. Die Vorschau
  zeigt vor dem Aktivieren die berechneten Zonen.
- **DPI-korrekte Koordinaten:** Die App aktiviert Per-Monitor-DPI-Awareness,
  damit berechnete Pixel auch bei 125 % oder 150 % Windows-Skalierung echte
  physische Pixel bleiben.
- **Automatisches Warten:** Ist das Spiel noch nicht offen, bleibt der Schalter
  an und FellSplit Pro wartet. Ein fehlendes Fenster ist kein Programmfehler.
- **Automatische Spiel-Erkennung:** Ein grosses, stabiles Vordergrundfenster
  wird automatisch erkannt. OBS, Browser, Desktop, bekannte Launcher und
  Systemfenster stehen auf einer Schutzliste. Weitere Prozesse lassen sich in
  den Einstellungen ausschliessen.
- **Alt-Tab-sicher:** Beim Fokuswechsel wird `ClipCursor` sofort geloest. Auch
  der optionale Topmost-Zustand wird temporaer entfernt, sodass OBS normal nach
  vorn kommt. Beim Zurueckwechseln wird beides wieder aktiviert.
- **Taskleisten-Fokusmodus:** Solange das Spiel im Vordergrund ist, werden die
  Explorer-Taskleisten vollstaendig verborgen und vom Watchdog verborgen
  gehalten. Beim Wechsel zu OBS, Alt+Tab, Ausschalten oder Beenden wird der
  vorherige Sichtbarkeitszustand wiederhergestellt.
- **Verifizierter Resize:** FellSplit Pro entfernt auch einen haengengebliebenen
  Maximiert-Status, erzwingt die Zielgroesse synchron und misst das Ergebnis
  mit `GetWindowRect` nach. Der Maus-Lock wird erst aktiviert, wenn Position und
  Groesse wirklich stimmen. Ignoriert ein Spiel den Resize, zeigt die App
  **Fenster wird angepasst** und laesst die Maus sicher frei.
- **Echte Clientflaechen-Pruefung:** Neben der aeusseren Fensterkante misst
  FellSplit Pro die tatsaechliche Zeichenflaeche. Eine noch sichtbare Titelleiste
  wie auf einem normalen Windows-Fenster wird erkannt und erneut entfernt.
- **Dual-Zone ohne PBP:** Ein zweites ausgewaehltes Fenster wird unabhaengig
  rahmenlos in der berechneten zweiten Zone gehalten. Der Monitor bleibt dabei
  ein einzelner Windows-Desktop; FellSplit Pro schaltet weder Aufloesung, HDR
  noch Bildwiederholrate um. Ob ein bestimmtes Spiel HDR im normalen
  Fenstermodus anbietet, entscheidet das Spiel selbst.
- **Bedienbares OBS:** Solange das Spiel aktiv ist, bleibt OBS in seiner Zone
  rahmenlos. Erhaelt OBS per Alt+Tab oder Mausklick den Fokus, stellt FellSplit
  Pro voruebergehend die normale Fensterleiste mit dem Schliessen-X wieder her.
- **Wiederanheften:** Wird das Spiel geschlossen und erneut gestartet, findet
  FellSplit Pro es ueber Prozessname/Fenstertitel wieder.
- **Reversible Aenderungen:** Vor dem Eingriff werden Stil, erweiterter Stil,
  Position und `WINDOWPLACEMENT` gespeichert. Beim Ausschalten werden sie
  standardmaessig wiederhergestellt.
- **Watchdog:** Optional wird die Zielposition regelmaessig erneut gesetzt,
  falls ein Spiel seine Fenstergroesse selbst zuruecksetzt.
- **Sicherer Hotkey:** Windows `RegisterHotKey` wird ohne Tastatur-Hook genutzt.
- **Konfiguration:** Die Einstellungen liegen unter
  `%APPDATA%\FellSplit Pro\config.json`; ein alter SplitLock-Stand wird
  automatisch uebernommen.
- **Tray und Autostart:** Schliessen oder Minimieren kann FellSplit Pro in den
  System-Tray verschieben. Der optionale Autostart verwendet den Run-Eintrag
  des aktuellen Windows-Benutzers und braucht keine Administratorrechte.
- **Einzelinstanz:** Ein zweiter versehentlicher Start wird blockiert.

## Wichtige Optionen

### Alt-Tab-sicherer Maus-Lock

Diese Option ist ab Version 1.1 standardmaessig aktiv. Solange das Spiel den
Fokus hat, bleibt die Maus strikt in der Spielzone. Sobald Alt+Tab den Fokus
wechselt, wird sie freigegeben und beim Zurueckwechseln wieder gesperrt. Vorhandene
Version-1.0-Einstellungen werden automatisch auf dieses sichere Verhalten
migriert.

### Immer im Vordergrund

Diese Option kann helfen, wenn die Taskleiste ueber dem Spielrand liegt. Ab 1.1
wird Topmost waehrend Alt+Tab automatisch geloest und danach wieder gesetzt.

### Dual-Zone fuer OBS

Dual-Zone behandelt das Spiel und OBS als zwei getrennte verwaltete Fenster:

- Der ausgewaehlte Monitor wird bei jeder Aktivierung neu aufgeloest.
- Automatik berechnet Spiel- und zweite Zone passend zur Monitoraufloesung.
- Spielseite links oder rechts ist frei waehlbar.
- Rahmen und Titelleisten werden fuer beide Fenster separat entfernt.
- Bei OBS-Fokus wird dessen Fensterleiste standardmaessig eingeblendet; nach
  dem Zurueckwechseln ins Spiel verschwindet sie automatisch wieder.
- Beim Ausschalten werden Stil und vorherige Position beider Fenster
  wiederhergestellt.
- Der Maus-Lock gilt nur fuer das Spiel und wird bei Alt+Tab freigegeben.

Das ist eine Fenstereinteilung, keine virtuelle Display-Treiber-Loesung. Spiele
sehen Windows weiterhin als einen einzigen Monitor mit dessen kompletter
Desktopaufloesung. Deshalb muss das Spiel fuer die berechnete interne
Zonenaufloesung den normalen Fenstermodus nutzen. Ein spieleigener randloser
Vollbildmodus darf weiterhin die gesamte Desktopaufloesung anzeigen, weil er
sich absichtlich daran orientiert.

### System-Tray und Windows-Autostart

Mit aktivem Tray minimiert das X die App standardmaessig nur neben die Uhr. Zum
wirklichen Beenden im Tray-Rechtsklickmenue **Beenden** waehlen. Optional kann
FellSplit Pro bei der Windows-Anmeldung unsichtbar starten und die Automatik direkt
aktivieren. Verschiebe den Programmordner danach nicht mehr, sonst zeigt der
Autostart noch auf den alten Pfad; erneutes Speichern korrigiert ihn.

### Als Administrator starten

Windows verhindert aus Sicherheitsgruenden, dass ein normal gestartetes
Programm Fenster eines hoeher privilegierten Prozesses veraendert. Wenn das
Spiel oder dessen Launcher als Administrator laeuft, nutze in FellSplit Pro den
Knopf **Als Administrator neu starten**.

## Eigenstaendige EXE und Installer bauen

Der Build muss auf einem 64-Bit-Windows-PC erfolgen. Starte fuer die komplette
Auslieferung einfach `build_installer.bat` per Doppelklick. Das Skript:

1. installiert beziehungsweise aktualisiert die Python-Build-Abhaengigkeiten,
2. erstellt die fensterlose App mit PyInstaller,
3. installiert Inno Setup 6 bei Bedarf ueber `winget`,
4. baut den deutschsprachigen Setup-Assistenten.

Das fertige Installationsprogramm liegt danach hier:

```text
installer\FellSplit-Pro-Setup-1.3.0.exe
```

Nur die portable EXE-Ausgabe erstellst du mit `build_exe.bat`. Sie liegt hier:

```text
dist\FellSplitPro.exe
```

Bei portabler Verteilung reicht diese einzelne EXE; bei normaler Verteilung die
einzelne Setup-EXE. Auf dem Ziel-PC ist in beiden Faellen keine
Python-Installation notwendig. PyInstaller bettet Python, CustomTkinter, Pillow
und die App-Ressourcen direkt in `FellSplitPro.exe` ein. Beim Start werden die
Laufzeitdateien kurz in einen temporaeren Windows-Ordner entpackt. Das kann den
Start um wenige Sekunden verlaengern, veraendert aber weder FPS noch HDR oder
die laufende Spieleleistung.

Nach der Installation ist der sichtbare Programmordner so aufgeraeumt wie bei
FellClicker Pro:

```text
FellSplitPro.exe
unins000.dat
unins000.exe
```

Die Notfall-Freigabe bleibt als Startmenue-Eintrag erhalten. Sie startet
`FellSplitPro.exe --emergency-unlock`, gibt den Cursor frei und blendet die
Taskleiste wieder ein, ohne zusaetzliche BAT- oder PowerShell-Dateien im
Installationsordner abzulegen.

Die EXE und der Installer tragen Name, Version, Herausgeber und das
FellSplit-Pro-Icon in ihren Windows-Dateieigenschaften. Windows SmartScreen kann
bei selbst erstellten, nicht digital signierten Programmen trotzdem eine
Warnung anzeigen. Ein vertrauenswuerdiges Code-Signing-Zertifikat ist der
professionelle Weg, die Herausgeberidentitaet nachzuweisen und Reputation ueber
mehrere Versionen aufzubauen; eine sofortige Warnungsfreiheit garantiert aber
auch eine neue gueltige Signatur nicht.

### Windows-SmartScreen-Warnung

Die Meldung **Windows hat den PC geschuetzt** ist in diesem Fall normalerweise
keine gefundene Schadsoftware, sondern eine SmartScreen-Reputationswarnung fuer
eine neue oder unbekannte EXE. FellSplit Pro kann und darf diese
Windows-Sicherheitsabfrage nicht selbst wegklicken.

Ohne eine oeffentlich vertrauenswuerdige digitale Signatur laesst sich die
Warnung bei Downloads auf fremden PCs nicht serioes oder garantiert verhindern.
Fuer eine professionelle Verteilung muessen sowohl `FellSplitPro.exe` als auch
der fertige Installer mit einem vertrauenswuerdigen Code-Signing-Dienst oder
-Zertifikat signiert und mit einem Zeitstempel versehen werden. Ein selbst
erstelltes Zertifikat reicht fuer fremde PCs nicht. Auch eine neue gueltige
Signatur kann anfangs noch eine Warnung erhalten, bis Microsoft ausreichend
positive Reputation fuer Datei beziehungsweise Herausgeber aufgebaut hat.

Falls Microsoft eine saubere Datei faelschlich als Schadsoftware oder
unerwuenschte Anwendung erkennt, kann genau diese Build-Datei beim offiziellen
Microsoft-Sicherheitsportal zur erneuten Analyse eingereicht werden. Das ist
aber kein Ersatz fuer Code-Signierung und garantiert keine sofortige
SmartScreen-Reputation.

## Notfall-Freigabe der Maus

Bei normalem Ausschalten und Beenden ruft FellSplit Pro immer `ClipCursor(NULL)`
auf und stellt die Taskleiste wieder her. Fuer einen harten Absturz gibt es im
Windows-Startmenue **FellSplit Pro Notfall-Freigabe**. Diese Aktion verwendet
dieselbe EXE und benoetigt keine sichtbaren Hilfsdateien.

## Grenzen und ehrliche Hinweise

- Manche Spiele bauen ihr Hauptfenster nach einem Grafikmodus-Wechsel komplett
  neu auf. FellSplit Pro wartet dann auf das neue Fenster und heftet sich erneut an.
- Ein Spiel mit exklusivem Vollbild muss zuerst im Spiel auf Fenstermodus
  gestellt werden.
- FellSplit Pro kann einen einzelnen physischen Monitor nicht gegenueber DirectX
  als zwei echte Hardware-Monitore ausgeben. Dafuer waeren PBP mit zwei
  Eingangen oder ein Display-Treiber notwendig. PBP wird von FellSplit Pro nicht
  aktiviert, damit die bestehende HDR-/240-Hz-Konfiguration unangetastet bleibt.
- Spiele mit Raw Input koennen den sichtbaren Cursor selbst zentrieren oder
  verstecken. `ClipCursor` begrenzt den Windows-Cursor, kann aber kein
  spielspezifisches Raw-Input-Verhalten ueberschreiben.
- Geschuetzte, erhoehte oder bestimmte Store-/Anti-Cheat-Fenster koennen externe
  Stil-Aenderungen ablehnen. FellSplit Pro injiziert keinen Code und liest keinen
  Spielspeicher, aber die Regeln des jeweiligen Spiels gelten trotzdem.
- Eine vollkommen allgemeine Spielerkennung kann nie fehlerfrei erraten, ob
  jedes unbekannte Vollbildprogramm ein Spiel ist. Deshalb greift FellSplit Pro nur
  beim stabilen Vordergrundfenster zu und bietet eine Ausschlussliste. Fuer ein
  bestimmtes Spiel bleibt ein fest eingetragener Prozessname am praezisesten.
- Wird **Beim Ausschalten wiederherstellen** deaktiviert, bleibt das Spiel nach
  dem Ausschalten rahmenlos und an der gesetzten Position. Die Maus wird
  dennoch freigegeben.

## Tests fuer Entwickler

```powershell
py -m unittest discover -s tests -v
```

Der automatisierte Umfang umfasst 51 Tests, unter anderem 32:9- und
21:9-Berechnungen, Monitorpositionen mit negativen Koordinaten, die sichere
Migration alter Einstellungen und den Fehlerfall "Fenster ignoriert das Ziel,
Maus darf nicht gesperrt werden". Die echte Interaktion mit einem
Spiel-Fenster muss zusaetzlich auf einem Windows-Desktop geprueft werden.

## Urheberrecht und Nutzung

Copyright © 2026 Fell Entertainment. Alle Rechte vorbehalten.

Dieses Repository ist **nicht Open Source** und enthält bewusst keine
Open-Source-Lizenz. Der Quellcode darf auf GitHub angesehen werden. Eine
Erlaubnis zum Kopieren, Verändern, Weiterveröffentlichen, Weiterverteilen oder
Übernehmen in andere Projekte wird nicht erteilt. Davon unberührt bleiben
zwingende gesetzliche Rechte und die für öffentliche Repositories geltenden
GitHub-Nutzungsbedingungen.

Die von Fell Entertainment offiziell veröffentlichten, unveränderten Releases
dürfen heruntergeladen, installiert und bestimmungsgemäß verwendet werden.
Weitere Einzelheiten stehen in [COPYRIGHT.md](COPYRIGHT.md).
