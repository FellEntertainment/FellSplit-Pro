# Aenderungen

## 1.3.0

- Feste 5120-x-1440-Zielwerte durch monitorabhaengige Layoutprofile ersetzt.
- Neue Standardoption **Automatisch passend**: 32:9 wird in zwei 16:9-Haelften
  geteilt; bei 21:9 erhaelt das Spiel eine 16:9-Zone und das zweite Fenster die
  verbleibende Flaeche.
- Zusaetzliche explizite Modi **50/50**, **Spiel 16:9 + Restflaeche** und
  **Benutzerdefiniert (Pixel)**.
- Alle aktiven Windows-Monitore werden mit Aufloesung, Position und Geraetename
  erkannt. Hauptmonitor oder ein bestimmtes Display sind auswaehlbar.
- Spiel kann links oder rechts platziert werden; die zweite Zone wechselt
  automatisch auf die jeweils andere Seite.
- Neue grafische Layoutvorschau mit berechneten Aufloesungen und Koordinaten.
- Unterstuetzung fuer Monitore links oder oberhalb des Hauptmonitors inklusive
  negativer virtueller Desktopkoordinaten.
- Bestehende 1.2.2-Standardwerte werden automatisch zum neuen Automatikprofil;
  abweichende eigene Pixelwerte bleiben als benutzerdefiniertes Layout erhalten.
- Konfigurationsschema 6 und 50 automatisierte Tests.

## 1.2.2

- Komplettes Produkt-Rebranding zu **FellSplit Pro** mit eigenem App-Icon,
  `FellSplitPro.exe`, Windows-Versionsinformationen und deutschsprachigem
  Inno-Setup-Installer.
- PyInstaller-Auslieferung auf eine einzelne OneFile-EXE umgestellt. Der
  installierte Ordner enthaelt dadurch keinen sichtbaren `_internal`-Ordner und
  keine Dokumentations- oder Notfall-Hilfsdateien mehr.
- Die Notfall-Freigabe ist als Parameter derselben EXE integriert; der
  Startmenue-Eintrag bleibt erhalten.
- Die Auswahl des Installationspfads wird im Setup immer angezeigt.
- Vorhandene SplitLock-Einstellungen und der alte Autostart-Eintrag werden
  automatisch auf FellSplit Pro migriert.
- Neue standardmaessig aktive Option **Fensterleiste bei OBS-Fokus zeigen**.
- Alt+Tab zu OBS stellt dessen Titelleiste mit Minimieren, Maximieren und X
  innerhalb der rechten Zone wieder her.
- Beim Zurueckwechseln ins Spiel wird OBS automatisch erneut rahmenlos und auf
  die komplette rechte Haelfte gesetzt.
- Das Schliessen von OBS ueber X wird erkannt; FellSplit Pro wartet danach auf
  einen spaeteren Neustart von OBS.
- Konfigurationsschema 5 und 37 automatisierte Tests.

## 1.2.1

- Neue standardmaessig aktive Option **Taskleiste beim Spielen verstecken**.
- Primaere und zusaetzliche Explorer-Taskleisten werden nur waehrend des
  Spielfokus verborgen und per Watchdog am Aufklappen gehindert.
- Alt+Tab, Fokus auf OBS, Ausschalten und Programmende stellen die vorherige
  Taskleisten-Sichtbarkeit wieder her.
- Die Notfall-Freigabe stellt jetzt neben dem Cursor auch die Taskleiste wieder
  her.
- Konfigurationsschema 4 und 28 automatisierte Tests.

## 1.2.0

- Neue Dual-Zone-Verwaltung fuer ein zweites Fenster wie OBS auf der rechten
  Bildschirmhaelfte, inklusive eigener Fensterauswahl, Koordinaten,
  Borderless-Umbau und Wiederherstellung.
- Preset fuer Spiel links und OBS rechts auf einem einzelnen
  5120-x-1440-Desktop; PBP wird nicht verwendet und die HDR-/240-Hz-
  Monitorkonfiguration nicht veraendert.
- FellSplit Pro misst nun neben dem aeusseren Fensterrechteck auch die echte
  Clientflaeche. Eine verbliebene oder vom Spiel erneut erzeugte Titelleiste
  gilt nicht mehr faelschlich als erfolgreicher 2560-x-1440-Resize.
- Rahmen und Titelleiste werden durch den Watchdog erneut entfernt, falls ein
  Spiel sie nach einem Grafikmodus-Wechsel wieder hinzufuegt.
- Der Maus-Failsafe ruft bei einer unbestaetigten Clientflaeche die Freigabe
  bedingungslos auf.
- Versionsnummer und Quellpfad stehen im Sitzungsprotokoll; auch das Tray zeigt
  die aktive Version. Beim Start trotz alter Tray-Instanz erscheint ein
  deutlicher Update-Hinweis.
- Konfigurationsschema 3 und 26 automatisierte Tests.

## 1.1.1

- Maximierte beziehungsweise aus Borderless-Fullscreen stammende Fenster
  werden vor dem Resize explizit in den Normalzustand versetzt; die Stilbits
  `WS_MAXIMIZE` und `WS_MINIMIZE` bleiben nicht mehr versehentlich erhalten.
- Die Positionierung erfolgt synchron und erhaelt mit `MoveWindow` einen
  zweiten, staerkeren Resize-Schritt fuer hartnaeckige Spiele.
- Die tatsaechliche Fensterposition wird nach jedem Eingriff ueber
  `GetWindowRect` verifiziert.
- `ClipCursor` wird nur noch aktiviert, wenn das gemessene Fenster wirklich am
  Ziel liegt. Bei einem weiterhin 5120 x 1440 grossen Fenster bleibt die Maus
  frei und die GUI zeigt **Fenster wird angepasst**.
- Aggressive Resize-Versuche pausieren bei Fokusverlust, damit Alt+Tab kein
  minimiertes Spiel wiederherstellt.
- Drei Regressionstests fuer Vollmonitor-Fenster, erfolgreiche Force-Resizes
  und die Win32-Resize-Sequenz ergaenzt; insgesamt 21 Tests.

## 1.1.0

- Maus-Lock wird bei Alt+Tab, Windows-Taste und jedem anderen Fokusverlust
  automatisch geloest und beim Zurueckkehren wieder aktiviert.
- Der optionale Topmost-Zustand wird beim Fokusverlust temporaer entfernt.
- Bestehende 1.0-Konfigurationen werden automatisch auf den sicheren
  Fokus-Modus migriert.
- Automatische Erkennung grosser, stabiler Spiel-Fenster mit Schutzliste fuer
  OBS, Browser, Desktop, Launcher und gaengige Arbeitsprogramme.
- Eigene Ausschlussliste fuer die automatische Erkennung.
- System-Tray mit Oeffnen, Aktivieren/Deaktivieren und echtem Beenden.
- Schliessen und Minimieren in den Tray.
- Optionaler Windows-Autostart pro Benutzer und unsichtbarer Tray-Start.
- Option, die Automatik direkt beim App-Start einzuschalten.
- Fensterloser Python-Start ueber `FellSplitPro.pyw`; die Batch-Datei laesst keine
  Eingabeaufforderung mehr offen.
- Zweiter Programmstart oeffnet die bereits laufende Tray-Instanz.
- Tray-Abhaengigkeiten werden vom Schnellstart und PyInstaller-Build erfasst.
- Testumfang von 8 auf 15 automatisierte Tests erweitert.

## 1.0.0

- Erste Version mit Borderless-Modus, Positionierung, Maus-Clipping,
  Wiederherstellung, Fensterauswahl und globalem Hotkey.
