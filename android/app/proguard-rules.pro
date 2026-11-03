# kotlinx.serialization and OkHttp ship their own R8 rules; keep the app's serializable models' names readable in crash reports.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
