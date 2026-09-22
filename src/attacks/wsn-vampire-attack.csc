<?xml version='1.0' encoding='utf-8'?>
<simconf version="2023090101">
  <simulation>
    <title>wsn-vampire-attack</title>
    <speedlimit>1.0</speedlimit>
    <randomseed>123456</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
      org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>50.0</transmitting_range>
      <interference_range>50.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>1.0</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>40000</logoutput>
    </events>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>Sink</description>
      <source>[CONFIG_DIR]/../nodes/sink.c</source>
      <commands>make sink.cooja TARGET=cooja</commands>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="49.53055877517954" y="49.530558775179536" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>1</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="486.3862044802067" y="59.85826572122966" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>27</id>
        </interface_config>
      </mote>
    </motetype>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>Vampire Attacker</description>
      <source>[CONFIG_DIR]/../nodes/vampire_node.c</source>
      <commands>make vampire_node.cooja TARGET=cooja</commands>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="473.69300709077766" y="61.34432185883406" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>29</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="36.680537606431216" y="36.95848429573965" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>53</id>
        </interface_config>
      </mote>
    </motetype>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>Sensor node</description>
      <source>[CONFIG_DIR]/../nodes/node.c</source>
      <commands>make node.cooja TARGET=cooja</commands>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="68.89152322298115" y="40.44626243343839" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>2</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="34.37905630933609" y="45.8364942463653" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>3</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="17.714975276232956" y="15.81307139061625" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>4</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="463.3994908691145" y="88.19260867576678" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>5</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="64.99811261867218" y="57.86502897661586" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>6</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="14.067148170870574" y="51.24664734892276" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>7</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="42.00564570502713" y="26.496378339901838" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>8</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="20.46300493168689" y="64.6258567608163" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>9</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="10.24" y="25.03" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>10</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="61.49331545498322" y="44.28117550359081" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>11</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="33.517631981423115" y="20.015023644221692" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>12</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="63.05386889776861" y="71.50360998109707" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>13</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="23.714703601014957" y="76.98604604525504" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>14</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="50.589056309336094" y="66.45111755035909" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>15</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="15.773621660098154" y="36.87915145866184" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>16</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="42.54113030890554" y="16.401424835019366" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>17</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="60.22375832369933" y="26.89285182912942" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>18</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="38.67412248204597" y="58.40647348922758" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>19</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="24.34082778420046" y="26.774180435277696" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>20</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="25.191829428096085" y="50.76747513312321" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>21</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="462.68690528999906" y="71.72663819802159" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>22</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="51.45435429497287" y="33.3748758740584" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>23</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="48.81198894259307" y="77.75399914943023" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>24</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="35.63797703461638" y="79.00799404601166" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>25</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="33.61379551979333" y="67.9362624334384" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>26</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="463.11806634444156" y="37.91538145596143" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>30</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="503.6658636798621" y="49.36194533455954" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>31</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="470.63" y="77.77" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>32</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="452.5510016438956" y="43.29674249824851" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>33</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="486.31748205216905" y="31.65373064751571" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>34</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="482.0691142625678" y="45.797185366964605" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>35</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="509.80414323918365" y="65.22329469784552" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>36</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="492.34167632553863" y="97.37005795323171" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>37</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="515.7824089604132" y="57.811502465843446" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>38</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="476.6137955197933" y="94.20973099097908" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>39</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="481.835240032405" y="73.55073263487472" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>40</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="493.92718536696464" y="81.02217714748643" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>41</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="510.0093832715887" y="77.50849753415655" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>42</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="503.8682657212297" y="91.81911426256782" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>43</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="495.04878730031515" y="39.74105267808146" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>44</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="457.18537669600624" y="58.51370037046758" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>45</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="453.34685840471195" y="82.99362166009817" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>46</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="493.6319081384656" y="68.65826572122964" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>47</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="473.42919081384656" y="34.44522143435805" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>48</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="466.9757988075846" y="97.91273592266599" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>49</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="449.27356370686647" y="62.353679613329874" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>51</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="501.5205656942255" y="60.59191981746663" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>52</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="51.79247603773315" y="21.050250474364844" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>54</id>
        </interface_config>
      </mote>
    </motetype>
  </simulation>
  <plugin>
    org.contikios.cooja.plugins.ScriptRunner
    <plugin_config>
      <script>var FileWriter = Java.type("java.io.FileWriter");
var FileReader = Java.type("java.io.FileReader");
var BufferedReader = Java.type("java.io.BufferedReader");
var File = Java.type("java.io.File");

var fileIndex = 1;
var lineCount = 0;
var maxLines = 50000;
var logFile = new FileWriter("E:/Projects/Projects/WSN_dacntt/wsn_dacntt/src/data/logs/run_" + fileIndex + ".log", false);
var cmdFile = new File("E:/Projects/Projects/WSN_dacntt/wsn_dacntt/src/data/logs/attack.cmd");

TIMEOUT(3600000, logFile.close(); log.testOK(););

while (true) {
    YIELD();
    try {
        logFile.write(time + " ID:" + id + " " + msg + "\n");
        logFile.flush();
        lineCount++;
        
        if (lineCount &gt;= maxLines) {
            logFile.close();
            fileIndex++;
            lineCount = 0;
            logFile = new FileWriter("E:/Projects/Projects/WSN_dacntt/wsn_dacntt/src/data/logs/run_" + fileIndex + ".log", false);
        }
        
        // --- C&amp;C File Bridge Logic ---
        if (cmdFile.exists()) {
            var reader = new BufferedReader(new FileReader(cmdFile));
            var cmd = reader.readLine();
            reader.close();
            if (cmd != null &amp;&amp; cmd.length() &gt; 0) {
                var strCmd = new java.lang.String(cmd);
                if (strCmd.startsWith("START_VNA") || strCmd.startsWith("STOP_VNA")) {
                    var m29 = sim.getMoteWithID(29);
                    if (m29 != null) write(m29, cmd);
                    var m53 = sim.getMoteWithID(53);
                    if (m53 != null) write(m53, cmd);
                } else {
                    var m53 = sim.getMoteWithID(53);
                    if (m53 != null) write(m53, cmd);
                }
            }
            cmdFile.delete();
        }
        // -----------------------------
        
    } catch (e) {
        logFile.close();
        throw e;
    }
}
</script>
      <active>true</active>
    </plugin_config>
    <bounds x="1" y="1" height="600" width="600" z="2" />
  </plugin>
  <plugin>
    org.contikios.cooja.plugins.LogListener
    <plugin_config>
      <filter />
      <formatted_time />
      <coloring />
    </plugin_config>
    <bounds x="400" y="160" height="240" width="1308" z="1" />
  </plugin>
  <plugin>
    org.contikios.cooja.plugins.Visualizer
    <plugin_config>
      <moterelations>true</moterelations>
      <skin>org.contikios.cooja.plugins.skins.IDVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.GridVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.TrafficVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.UDGMVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.MoteTypeVisualizerSkin</skin>
      <viewport>0.5944975270128645 0.0 0.0 0.5944975270128645 -1.2729769502549209 119.713114416779</viewport>
    </plugin_config>
    <bounds x="405" y="452" height="400" width="400" />
  </plugin>
</simconf>