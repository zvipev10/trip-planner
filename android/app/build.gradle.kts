plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}
android {
    namespace = "com.tripplanner"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.tripplanner"
        minSdk = 26
        targetSdk = 35
        versionCode = 10
        versionName = "0.5.4"
    }
    buildFeatures { compose = true; buildConfig = true }
    val stableStore = System.getenv("TRIP_SIGNING_STORE")
    val stablePassword = System.getenv("TRIP_SIGNING_PASSWORD")
    if (!stableStore.isNullOrBlank()) {
        require(!stablePassword.isNullOrBlank()) { "Stable signing password is required." }
        signingConfigs.create("stable") {
            storeFile = file(stableStore)
            storePassword = stablePassword
            keyAlias = "tripplanner"
            keyPassword = stablePassword
        }
    }
    buildTypes {
        debug {
            if (!stableStore.isNullOrBlank()) signingConfig = signingConfigs.getByName("stable")
            buildConfigField("String", "API_URL", "\"http://151.145.93.180/trip-planner/\"") }
        release { buildConfigField("String", "API_URL", "\"\"") }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
ksp { arg("room.schemaLocation", "$projectDir/schemas") }
dependencies {
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    implementation(platform("androidx.compose:compose-bom:2025.04.01"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.0")
    implementation("androidx.room:room-runtime:2.7.1")
    implementation("androidx.room:room-ktx:2.7.1")
    ksp("androidx.room:room-compiler:2.7.1")
}

// Share the pinned map renderer and license with the web app, without a CDN.
val syncRouteMapAssets by tasks.registering(Copy::class) {
    from(rootProject.projectDir.parentFile.resolve("backend/app/web")) {
        include("leaflet.js", "leaflet.css", "leaflet-LICENSE.txt", "route-map.mjs", "core.mjs")
    }
    into(layout.buildDirectory.dir("generated/mapAssets/map"))
}
android.sourceSets.getByName("main").assets.srcDir(layout.buildDirectory.dir("generated/mapAssets"))
tasks.named("preBuild") { dependsOn(syncRouteMapAssets) }
