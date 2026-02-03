# Use the latest Alpine Linux as the base
FROM alpine:latest

# Install FRRouting, OpenRC, and IPtables
RUN apk update && apk add --no-cache \
    frr \
    frr-openrc \
    ip6tables \
    iptables \
    bash \
    vim

# Enable IP forwarding (required for a router)
RUN echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf

# Enable FRR daemons (BGP and OSPF)
# We modify the daemons file to enable bgpd and ospfd by default
RUN sed -i 's/bgpd=no/bgpd=yes/' /etc/frr/daemons && \
    sed -i 's/ospfd=no/ospfd=yes/' /etc/frr/daemons && \
    sed -i 's/zebra=no/zebra=yes/' /etc/frr/daemons

# Create the entry point logic (optional, but good for keeping container alive)
CMD ["/bin/sh", "-c", "/usr/lib/frr/frrinit.sh start && tail -f /dev/null"]