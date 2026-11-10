import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// The web app in ../stride is the single source of truth; it is copied into the APK at build time.
val webAssets = layout.buildDirectory.dir("generated/webAssets")
val syncWebAssets = tasks.register<Sync>("syncWebAssets") {
    from(rootProject.file("../stride")) {
        include("index.html", "manifest.webmanifest", "css/**", "js/**", "icons/**")
    }
    into(webAssets)
}

android {
    namespace = "com.likki.stride"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.likki.stride"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.2.0"
    }

    signingConfigs {
        // Fixed sideload key so every build can update the installed app without wiping its data.
        getByName("debug") {
            storeFile = rootProject.file("sideload.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    sourceSets["main"].assets.srcDir(webAssets)

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = true
        warningsAsErrors = false
    }
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

tasks.named("preBuild") { dependsOn(syncWebAssets) }

dependencies {
    implementation("androidx.health.connect:connect-client:1.1.0")
    implementation("androidx.webkit:webkit:1.14.0")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.core:core-ktx:1.16.0")
    testImplementation("junit:junit:4.13.2")
}
