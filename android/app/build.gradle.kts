import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// Release signing and server address come from android/keystore.properties (not in Git) or the environment.
val keystore = Properties().apply {
    val file = rootProject.file("keystore.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
fun setting(name: String, env: String): String? = keystore.getProperty(name) ?: System.getenv(env)

android {
    namespace = "de.schimmelpilz.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "de.schimmelpilz.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    signingConfigs {
        val storeFile = setting("storeFile", "SCHIMMELPILZ_KEYSTORE")
        if (storeFile != null) {
            create("release") {
                this.storeFile = file(storeFile)
                storePassword = setting("storePassword", "SCHIMMELPILZ_KEYSTORE_PASSWORD")
                keyAlias = setting("keyAlias", "SCHIMMELPILZ_KEY_ALIAS")
                keyPassword = setting("keyPassword", "SCHIMMELPILZ_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            // Emulator alias for a server running on the development machine (uvicorn --port 8001).
            buildConfigField("String", "API_BASE_URL", "\"${setting("debugApiUrl", "SCHIMMELPILZ_DEBUG_API_URL") ?: "http://10.0.2.2:8001/"}\"")
        }
        release {
            val url = setting("apiUrl", "SCHIMMELPILZ_API_URL") ?: "https://example.com/"
            require(url.startsWith("https://")) { "Release builds must use an https:// server address" }
            buildConfigField("String", "API_BASE_URL", "\"$url\"")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
        unitTests.isIncludeAndroidResources = true
        unitTests.all { test ->
            // Screenshot run against a live server: ./gradlew :app:testDebugUnitTest -Pscreenshots=<folder> (see android/README.md).
            (project.findProperty("screenshots") as String?)?.let { test.systemProperty("schimmelpilz.screenshots", it) }
            listOf("email", "password").forEach { key -> (project.findProperty("demo.$key") as String?)?.let { test.systemProperty("schimmelpilz.demo.$key", it) } }
            // Optional mirror for the Android system images Robolectric downloads (e.g. when Maven Central rate-limits).
            (project.findProperty("robolectricRepo") as String?)?.let { test.systemProperty("robolectric.dependency.repo.url", it) }
        }
    }
}

kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.core.splashscreen)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.mlkit.document.scanner)
    implementation(libs.androidx.work.runtime)
    debugImplementation(libs.compose.ui.tooling)
    debugImplementation(libs.compose.ui.test.manifest)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
}
