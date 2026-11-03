package de.schimmelpilz.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ServerTest {
    @Test fun homeNetworkAddressesUseHttp() {
        assertEquals("http://192.168.1.20:8001/", Server.normalize("192.168.1.20:8001"))
        assertEquals("http://10.0.0.5:8001/", Server.normalize(" 10.0.0.5:8001/ "))
        assertEquals("http://172.20.1.2:8001/", Server.normalize("172.20.1.2:8001"))
        assertEquals("http://100.116.115.30:8001/", Server.normalize("100.116.115.30:8001"))
    }

    @Test fun domainsUseHttpsAndKeepExplicitScheme() {
        assertEquals("https://kanzlei.example.de/", Server.normalize("kanzlei.example.de"))
        assertEquals("https://100.200.1.2/", Server.normalize("100.200.1.2"))
        assertEquals("https://kanzlei.example.de/", Server.normalize("https://kanzlei.example.de/app?x=1"))
        assertEquals("http://pc.local:8001/", Server.normalize("http://pc.local:8001"))
    }

    @Test fun rejectsNonsense() {
        assertNull(Server.normalize(""))
        assertNull(Server.normalize("   "))
        assertNull(Server.normalize("ftp://x"))
    }
}
