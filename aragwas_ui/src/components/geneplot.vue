<template>
    <div>
        <svg id="chart" height="500" width="100%" ref="svg">
        </svg>
    </div>
</template>

<script lang="ts">
    import * as d3 from "d3";
    import Vue from "vue";
    import {Component, Prop, Watch} from "vue-property-decorator";

    @Component({
        name: "gene-plot",
        props: ["dataPoints", "options"],
    })
    export default class GenePlot extends Vue {
        @Prop()
        dataPoints;
        @Prop()
        options;
        mounted() {
            const padding = 40;
            const w = this.options.width;
            let w_rect = this.options.w_rect;
            if (typeof w_rect === "undefined") {
                w_rect = 400;
            }
            let rect_center = this.options.rect_center;
            if (typeof rect_center === "undefined") {
                rect_center = w / 2;
            }
            const h = 450;
            const scaleW = d3.scaleLinear();
            const scaleH = d3.scaleLinear();

            const defaultOptions = {
                matrix: undefined,
                species_id: undefined,
                chr: undefined,
                alpha: 0.05,
                max_y: 15,
                min_x: 3047810,
                max_x: 5081540,
                bonferoniThreshold: 10,
                div: undefined,
                divLegend: undefined,
                xlabel: "x",
                ylabel: "y",
                legend1: "",
                legend2: "",
                color: this.options.chr,
                limited: 0,
            };
            const options = this.options;
            // Add the missing parameters
            for (const key of Object.keys(defaultOptions)) {
                if (typeof options[key] === "undefined") {
                    options[key] = defaultOptions[key];
                }
            }

            // define scaling options
            scaleW.domain([options.min_x, options.max_x]);
            scaleW.range([padding, (w - padding)]);
            scaleH.domain([0, options.max_y + 1]);
            scaleH.range([h - padding, padding]);

            // define colors
            const blue = 204 - (options.color) * 40;
            const red = 51 + (options.color) * 40;
            // get data
            const data = options.matrix;
            const d2 = [[options.min_x, options.bonferoniThreshold], [options.max_x, options.bonferoniThreshold]];
            // draw svg
            const svg = d3.select(this.$refs.svg as Element)
                .append("svg")
                .attr("width", w)
                .attr("height", h);
            const dif = options.max_x - options.min_x;
            const len = Math.pow(10, ((String(Math.round(dif / 5)).length - 1)));
            const valX = Math.round(dif / (5 * len)) * len;
            // draw graph help-lines in background
            for (let i = 0; (options.min_x + valX * i) < options.max_x ; i++) {
                svg.append("svg:g")
                    .attr("transform", "translate(" + scaleW(options.min_x + valX * i) + "," + (h - padding / 1.5) + ")")
                    .append("text").text(options.min_x + valX * i)
                    .attr("text-anchor", "middle");
            }
            const valY = Math.round(options.max_y / 3);
            for (let i = 1; (i * valY) < (options.max_y + 1); i++) {
                svg.append("svg:g")
                    .attr("transform", "translate(" + (padding / 1.5) + "," + scaleH(valY * i) + ")")
                    .append("text").text(valY * i)
                    .attr("text-anchor", "middle");
            }
            // write text-information to axis and draw graph-elements
            svg.append("svg:g")
                .attr("transform", "matrix(0, -1, 1, 0, 0, 0)").append("svg:g")
                .attr("transform", "translate(" + ((-3 * padding)) + "," + (padding / 3) + ")")
                .append("text").text("-log10(p-value)");
            svg.append("svg:g")
                .attr("transform", "translate(" + ((w - padding) / 2) + "," + (h - padding / 5) + ")")
                .append("text").text("chromosomal position [Chr " + options.chr + "]")
                .attr("text-anchor", "middle");
            svg.append("rect")
                .attr("x", padding)
                .attr("y", padding / 2)
                .attr("width", padding / 2.5)
                .attr("height", padding / 3.5)
                .style("fill", "rgb(0,100,0)");
            svg.append("svg:g")
                .attr("transform", "translate(" + (padding + 25) + "," + (padding / 1.3) + ")")
                .append("text").text("Bonferroni threshold [" + options.alpha + "]");
            svg.append("svg:line")
                .attr("x1", scaleW(options.min_x))
                .attr("y1", scaleH(3))
                .attr("x2", scaleW(options.min_x))
                .attr("y2", scaleH(options.max_y + 1))
                .style("stroke", "#000000")
                .style("stroke-width", 1);
            svg.append("svg:line")
                .attr("x1", scaleW(options.min_x))
                .attr("y1", scaleH(0))
                .attr("x2", scaleW(options.max_x))
                .attr("y2", scaleH(0))
                .style("stroke", "#000000")
                .style("stroke-width", 1);
            svg.append("svg:line")
                .attr("x1", scaleW(d2[0][0]))
                .attr("y1", scaleH(d2[0][1]))
                .attr("x2", scaleW(d2[1][0]))
                .attr("y2", scaleH(d2[1][1]))
                .style("stroke", "rgb(0,100,0)")
                .style("stroke-width", 1.5 );
            // draw gene rectangle
            svg.append("svg:rect")
                .attr("x", rect_center - w_rect / 2)
                .attr("y", 350)
                .attr("width", w_rect)
                .attr("height", 50)
                .style("fill", "rgb(255,255,255)")
                .style("stroke", "rgb(0,100,0)")
                .style("stroke-width", 4);
            // draw datapoints
            svg.selectAll("circle")
                .data(this.dataPoints)
                .enter()
                .append("circle")
                .attr("cx", (d) => {
                    return scaleW(d[0]);
                })
                .attr("cy", (d) => {
                    return scaleH(d[1]);
                })
                .attr("r", 2.1)
                .style("fill", "rgb(" + red + ",102," + blue + ")");
        }
    }
</script>
<style >
    #chart {
        margin:25px;
    }
    #chart path {
        fill: transparent;
        stroke: green;
    }
</style>