#!/bin/bash
# Wrapper to redirect docker commands to podman
#
# Harbor hardcodes docker commands. This wrapper intercepts and translates
# them to podman, handling incompatibilities like unsupported flags and commands.
#
# Installation: cp infrastructure/docker-wrapper.sh ~/.bin/docker && chmod +x ~/.bin/docker
#               (or ~/bin/docker if you prefer)
#
# Usage: export PATH="$HOME/bin:$PATH" && harbor run ...

# If this is a compose command, use python podman-compose instead of podman's built-in
if [ "$1" = "compose" ]; then
    shift  # Remove 'compose'
    
    # Check for commands that need special handling
    if echo "$@" | grep -q " exec "; then
        # Harbor uses 'docker compose exec -it -e VAR=val' but podman-compose doesn't support -it
        # Convert to direct podman exec
        
        project=""
        container=""
        env_vars=()
        command=()
        i=0
        args=("$@")
        found_exec=false
        found_container=false
        
        while [ $i -lt ${#args[@]} ]; do
            if [ "${args[$i]}" = "-p" ]; then
                project="${args[$((i+1))]}"
                ((i+=2))
            elif [ "${args[$i]}" = "-f" ]; then
                ((i+=2))  # Skip -f and its value
            elif [ "${args[$i]}" = "exec" ]; then
                found_exec=true
                ((i++))
            elif [ "$found_exec" = true ]; then
                # Skip -it, -i, -t flags
                if [ "${args[$i]}" = "-it" ] || [ "${args[$i]}" = "-i" ] || [ "${args[$i]}" = "-t" ]; then
                    ((i++))
                elif [ "${args[$i]}" = "-e" ]; then
                    # Environment variable
                    env_vars+=("-e" "${args[$((i+1))]}")
                    ((i+=2))
                elif [ "$found_container" = false ]; then
                    # First non-flag arg is container name
                    container="${args[$i]}"
                    found_container=true
                    ((i++))
                else
                    # Everything else is the command
                    command=("${args[@]:$i}")
                    break
                fi
            else
                ((i++))
            fi
        done
        
        # Find the actual container name
        container_name=$(podman ps --format "{{.Names}}" | grep -i "$project" | grep -i "$container" | head -1)
        
        if [ -n "$container_name" ]; then
            # Execute the command with environment variables
            exec podman exec "${env_vars[@]}" "$container_name" "${command[@]}"
        else
            echo "Error: Could not find container for project=$project, container=$container" >&2
            podman ps >&2
            exit 1
        fi
    elif echo "$@" | grep -q " cp "; then
        # Extract project, src, dst from: -p PROJECT -f FILE cp SRC DST
        project=""
        src=""
        dst=""
        i=0
        args=("$@")
        
        while [ $i -lt ${#args[@]} ]; do
            if [ "${args[$i]}" = "-p" ]; then
                project="${args[$((i+1))]}"
            elif [ "${args[$i]}" = "cp" ]; then
                src="${args[$((i+1))]}"
                dst="${args[$((i+2))]}"
                break
            fi
            ((i++))
        done
        
        # Find running container by project name
        container_name=$(podman ps --format "{{.Names}}" | grep -i "$project" | grep -i "main" | head -1)
        
        if [ -z "$container_name" ]; then
            echo "Error: Could not find container for project $project" >&2
            podman ps >&2
            exit 1
        fi
        
        # Check if src or dst contains container reference (format: container:path)
        if [[ "$src" == *:* ]]; then
            # Copying FROM container
            src_path="${src#*:}"
            exec podman cp "$container_name:$src_path" "$dst"
        elif [[ "$dst" == *:* ]]; then
            # Copying TO container
            dst_path="${dst#*:}"
            # Create parent directory if needed
            parent_dir=$(dirname "$dst_path")
            podman exec "$container_name" mkdir -p "$parent_dir" 2>/dev/null || true
            exec podman cp "$src" "$container_name:$dst_path"
        else
            echo "Error: Neither src nor dst contains container reference" >&2
            exit 1
        fi
    else
        # Use python podman-compose for other commands
        exec podman-compose "$@"
    fi
fi

# For all other commands, pass through to podman
exec podman "$@"
