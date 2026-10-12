plugins { id("com.android.application"); id("org.jetbrains.kotlin.android"); id("com.chaquo.python") }

// Ta sama logika co na laptopie: kopiujemy moduły z ../autodiag_real (bez app.py/ui/updater – to interfejs Windows).
val copyDesktopLogic by tasks.registering(Copy::class) {
    from(rootProject.file("../autodiag_real")) {
        include("__init__.py", "me72.py", "me72_dtc.py", "bmw_dtc.py", "ds2.py", "modules_ro.py", "live.py", "coldstart.py", "extras.py", "version.py")
    }
    into(layout.buildDirectory.dir("desktop-python/autodiag_real"))
}

android {
    namespace = "pl.autodiag.real"
    compileSdk = 36
    defaultConfig {
        applicationId = "pl.autodiag.real"
        minSdk = 24
        targetSdk = 36
        versionCode = 3
        versionName = "1.3.4-android"
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64") }
    }
    // Stały klucz (sekret CI ANDROID_KEYSTORE_*), żeby kolejne wersje instalowały się jako aktualizacja bez kasowania danych.
    val ks = System.getenv("ANDROID_KEYSTORE_FILE")
    signingConfigs {
        if (ks != null) create("fixed") {
            storeFile = file(ks); storePassword = System.getenv("ANDROID_KEYSTORE_PASS")
            keyAlias = "autodiag"; keyPassword = System.getenv("ANDROID_KEYSTORE_PASS")
        }
    }
    buildTypes {
        getByName("release") { isMinifyEnabled = false; if (ks != null) signingConfig = signingConfigs.getByName("fixed") }
        getByName("debug") { if (ks != null) signingConfig = signingConfigs.getByName("fixed") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

chaquopy {
    defaultConfig { version = "3.11" }
    sourceSets { getByName("main") { srcDir("src/main/python"); srcDir(layout.buildDirectory.dir("desktop-python")) } }
}

tasks.matching { it.name.startsWith("merge") && it.name.endsWith("PythonSources") }.configureEach { dependsOn(copyDesktopLogic) }
tasks.named("preBuild") { dependsOn(copyDesktopLogic) }

dependencies {
    implementation("com.github.mik3y:usb-serial-for-android:3.8.1")
}
