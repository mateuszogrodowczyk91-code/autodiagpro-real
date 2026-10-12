plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "pl.autodiag.android"
    compileSdk = 35
    defaultConfig { applicationId = "pl.autodiag.kdcan"; minSdk = 24; targetSdk = 35; versionCode = 1; versionName = "0.1.0-kdcan" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation(project(":kdcan"))
    implementation("com.github.mik3y:usb-serial-for-android:3.8.1")
}
