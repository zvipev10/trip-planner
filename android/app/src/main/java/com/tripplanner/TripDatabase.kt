package com.tripplanner

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "trips")
data class Trip(
    @PrimaryKey val id: String,
    val title: String,
    val updatedAt: Long = System.currentTimeMillis(),
    val revision: Long = 0,
    val startId: String? = null,
    val endId: String? = null,
)

@Entity(
    tableName = "locations",
    foreignKeys = [ForeignKey(entity = Trip::class, parentColumns = ["id"], childColumns = ["tripId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("tripId")],
)
data class TripLocation(
    @PrimaryKey val id: String,
    val tripId: String,
    val name: String,
    val address: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val source: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
) {
    @get:Ignore
    val resolved: Boolean get() = latitude != null && longitude != null
}

data class TripSnapshot(@Embedded val trip: Trip, @Relation(parentColumn = "id", entityColumn = "tripId") val locations: List<TripLocation>)

data class TripSummary(@Embedded val trip: Trip, val locationCount: Int)

@Dao
abstract class TripDao {
    @Query("SELECT trips.*, (SELECT COUNT(*) FROM locations WHERE tripId = trips.id) AS locationCount FROM trips ORDER BY updatedAt DESC")
    abstract fun summaries(): Flow<List<TripSummary>>

    @Query("SELECT * FROM trips WHERE id = :id")
    abstract fun trip(id: String): Flow<Trip?>

    @Query("SELECT * FROM trips WHERE id = :id")
    abstract suspend fun findTrip(id: String): Trip?

    @Query("SELECT * FROM locations WHERE tripId = :tripId ORDER BY createdAt, id")
    abstract fun locations(tripId: String): Flow<List<TripLocation>>

    @Transaction
    @Query("SELECT * FROM trips WHERE id = :id")
    abstract suspend fun snapshot(id: String): TripSnapshot?

    @Insert abstract suspend fun insertTrip(trip: Trip)
    @Upsert abstract suspend fun upsertLocation(location: TripLocation)
    @Update abstract suspend fun updateTrip(trip: Trip)
    @Query("DELETE FROM locations WHERE id = :id AND tripId = :tripId")
    abstract suspend fun deleteLocationRow(id: String, tripId: String)

    @Transaction
    open suspend fun saveLocation(location: TripLocation) {
        val trip = requireNotNull(findTrip(location.tripId))
        upsertLocation(location)
        updateTrip(trip.copy(updatedAt = System.currentTimeMillis(), revision = trip.revision + 1))
    }

    @Transaction
    open suspend fun removeLocation(location: TripLocation) {
        val trip = requireNotNull(findTrip(location.tripId))
        deleteLocationRow(location.id, trip.id)
        updateTrip(trip.copy(
            startId = trip.startId.takeUnless { it == location.id },
            endId = trip.endId.takeUnless { it == location.id },
            updatedAt = System.currentTimeMillis(), revision = trip.revision + 1,
        ))
    }

    @Query("SELECT COUNT(*) FROM locations WHERE id = :locationId AND tripId = :tripId")
    abstract suspend fun locationExists(tripId: String, locationId: String): Int

    @Transaction
    open suspend fun setEndpoint(tripId: String, locationId: String, start: Boolean) {
        require(locationExists(tripId, locationId) == 1)
        val trip = requireNotNull(findTrip(tripId))
        updateTrip(trip.copy(
            startId = if (start) locationId else trip.startId,
            endId = if (start) trip.endId else locationId,
            updatedAt = System.currentTimeMillis(), revision = trip.revision + 1,
        ))
    }
}

@Database(entities = [Trip::class, TripLocation::class], version = 1, exportSchema = true)
abstract class TripDatabase : RoomDatabase() {
    abstract fun trips(): TripDao
    companion object {
        @Volatile private var instance: TripDatabase? = null
        fun get(context: Context): TripDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(context.applicationContext, TripDatabase::class.java, "trips.db")
                .build().also { instance = it }
        }
    }
}
