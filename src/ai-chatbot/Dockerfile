# Build stage
FROM maven:3.9.5-eclipse-temurin-17-alpine AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -B -e dependency:go-offline
COPY src ./src
RUN mvn -B -e package -DskipTests

# Run stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

# Healthcheck uses wget; keep runtime image minimal but functional.
RUN apk add --no-cache wget

COPY --from=build /app/target/app.jar app.jar

EXPOSE 4567

CMD ["java", "-jar", "app.jar"]
